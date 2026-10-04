package main

import (
	_ "embed"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"

	"github.com/brohd11/mcp-sh"
)

// pluginSrc is the GIMP plug-in, written into GIMP's plug-ins folder by
// `mcp-sh-gimp plugin install`, so the shell and the bridge it talks to always come from
// the same tag.
//
//go:embed plugin/mcp-sh-gimp-bridge/mcp-sh-gimp-bridge.py
var pluginSrc []byte

const (
	pluginName    = "mcp-sh-gimp-bridge" // folder and script name; GIMP needs them to match
	pluginUsage   = "plugin install|status|remove [--dir PLUGINS_DIR]"
	pluginSummary = "Install, check or remove the GIMP plug-in (the bridge mcp-sh-gimp talks to)"
)

func pluginCommand(version string) mcpsh.Subcommand {
	return mcpsh.Subcommand{
		Name: "plugin", Usage: pluginUsage, Summary: pluginSummary,
		Run: func(args []string, stdout, stderr io.Writer) int {
			return runPlugin(version, args, stdout, stderr)
		},
	}
}

func runPlugin(version string, args []string, stdout, stderr io.Writer) int {
	usage := func() int {
		fmt.Fprintf(stderr, "usage: mcp-sh-gimp %s\n", pluginUsage)
		return 2
	}
	if len(args) == 0 {
		return usage()
	}
	sub, dir := args[0], ""
	for i := 1; i < len(args); i++ {
		switch a := args[i]; {
		case a == "--dir" && i+1 < len(args):
			dir = args[i+1]
			i++
		case strings.HasPrefix(a, "--dir="):
			dir = strings.TrimPrefix(a, "--dir=")
		default:
			fmt.Fprintf(stderr, "unexpected argument %q\n", a)
			return usage()
		}
	}
	if sub != "install" && sub != "status" && sub != "remove" {
		return usage()
	}
	if dir == "" {
		var err error
		if dir, err = findPluginsDir(); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
	}
	var err error
	switch sub {
	case "install":
		err = installPlugin(dir, version, stdout)
	case "status":
		pluginStatus(dir, version, stdout)
	case "remove":
		err = removePlugin(dir, stdout)
	}
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

// gimpConfigBases are the folders holding GIMP's per-version config folders (3.0, 3.2, ...)
// on this OS, in order of preference.
func gimpConfigBases() []string {
	home, _ := os.UserHomeDir()
	switch runtime.GOOS {
	case "darwin":
		return []string{filepath.Join(home, "Library", "Application Support", "GIMP")}
	case "windows":
		return []string{filepath.Join(os.Getenv("APPDATA"), "GIMP")}
	}
	xdg := os.Getenv("XDG_CONFIG_HOME")
	if xdg == "" {
		xdg = filepath.Join(home, ".config")
	}
	return []string{
		filepath.Join(xdg, "GIMP"),
		filepath.Join(home, ".var", "app", "org.gimp.GIMP", "config", "GIMP"), // Flatpak
		filepath.Join(home, "snap", "gimp", "current", ".config", "GIMP"),     // Snap
	}
}

var gimpVersionDir = regexp.MustCompile(`^3\.(\d+)$`)

// findPluginsDir is the plug-ins folder of the newest GIMP 3.x config folder.
func findPluginsDir() (string, error) {
	var tried []string
	for _, base := range gimpConfigBases() {
		tried = append(tried, base)
		entries, err := os.ReadDir(base)
		if err != nil {
			continue
		}
		var minors []int
		for _, e := range entries {
			if m := gimpVersionDir.FindStringSubmatch(e.Name()); m != nil && e.IsDir() {
				n, _ := strconv.Atoi(m[1])
				minors = append(minors, n)
			}
		}
		if len(minors) > 0 {
			sort.Ints(minors)
			return filepath.Join(base, fmt.Sprintf("3.%d", minors[len(minors)-1]), "plug-ins"), nil
		}
	}
	return "", fmt.Errorf("no GIMP 3.x config folder in %s: start GIMP once, or pass --dir (Edit > Preferences > Folders > Plug-ins)", strings.Join(tried, ", "))
}

var bridgeVersion = regexp.MustCompile(`(?m)^BRIDGE_VERSION = "([^"]*)"`)

func installPlugin(dir, version string, stdout io.Writer) error {
	dest := filepath.Join(dir, pluginName)
	if installed, ok := readBridgeVersion(dest); ok && compareVersions(installed, version) > 0 {
		return fmt.Errorf("installed plug-in %s is newer than this binary (%s); update mcp-sh-gimp", installed, version)
	}
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return err
	}
	src := bridgeVersion.ReplaceAll(pluginSrc, []byte(`BRIDGE_VERSION = "`+strings.ReplaceAll(version, `"`, ``)+`"`))
	script := filepath.Join(dest, pluginName+".py")
	if err := os.WriteFile(script, src, 0o755); err != nil {
		return err
	}
	// WriteFile keeps the mode of an existing file; GIMP only runs executable plug-ins.
	if err := os.Chmod(script, 0o755); err != nil {
		return err
	}
	fmt.Fprintf(stdout, "Installed the mcp-sh-gimp plug-in %s in %s\n", version, dest)
	fmt.Fprintln(stdout, "Restart GIMP, then start it from Tools > mcp-sh-gimp > Start Bridge.")
	return nil
}

func pluginStatus(dir, version string, stdout io.Writer) {
	fmt.Fprintf(stdout, "plug-ins  %s\n", dir)
	switch installed, ok := readBridgeVersion(filepath.Join(dir, pluginName)); {
	case !ok:
		fmt.Fprintln(stdout, "plug-in   not installed: mcp-sh-gimp plugin install")
	case installed != version:
		fmt.Fprintf(stdout, "plug-in   %s, binary is %s: mcp-sh-gimp plugin install, then restart GIMP\n", installed, version)
	default:
		fmt.Fprintf(stdout, "plug-in   %s (matches the binary)\n", installed)
	}
}

func removePlugin(dir string, stdout io.Writer) error {
	dest := filepath.Join(dir, pluginName)
	if _, ok := readBridgeVersion(dest); !ok {
		if _, err := os.Stat(dest); errors.Is(err, os.ErrNotExist) {
			fmt.Fprintf(stdout, "No plug-in in %s\n", dest)
			return nil
		}
		return fmt.Errorf("%s is not the mcp-sh-gimp plug-in; not removing it", dest)
	}
	if err := os.RemoveAll(dest); err != nil {
		return err
	}
	fmt.Fprintf(stdout, "Removed %s. Restart GIMP to unload it.\n", dest)
	return nil
}

// readBridgeVersion reads the version stamped into the plug-in installed in dir.
func readBridgeVersion(dir string) (string, bool) {
	data, err := os.ReadFile(filepath.Join(dir, pluginName+".py"))
	if err != nil {
		return "", false
	}
	m := bridgeVersion.FindSubmatch(data)
	if m == nil {
		return "", false
	}
	return string(m[1]), true
}

// compareVersions compares the vMAJOR.MINOR.PATCH prefix of two versions, such as
// `git describe` output. It returns 0 when either has none ("dev"), so dev builds never
// block an install.
func compareVersions(a, b string) int {
	va, okA := parseVersion(a)
	vb, okB := parseVersion(b)
	if !okA || !okB {
		return 0
	}
	for i := range va {
		if va[i] != vb[i] {
			if va[i] > vb[i] {
				return 1
			}
			return -1
		}
	}
	return 0
}

var semverPrefix = regexp.MustCompile(`^v?(\d+)\.(\d+)\.(\d+)`)

func parseVersion(v string) ([3]int, bool) {
	var out [3]int
	m := semverPrefix.FindStringSubmatch(v)
	if m == nil {
		return out, false
	}
	for i := range out {
		out[i], _ = strconv.Atoi(m[i+1])
	}
	return out, true
}
