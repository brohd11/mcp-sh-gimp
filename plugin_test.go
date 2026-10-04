package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func runPluginCmd(t *testing.T, version string, args ...string) (string, string, int) {
	t.Helper()
	var out, errOut bytes.Buffer
	code := runPlugin(version, args, &out, &errOut)
	return out.String(), errOut.String(), code
}

func TestPluginInstallStatusRemove(t *testing.T) {
	dir := t.TempDir()
	if out, _, code := runPluginCmd(t, "v1.2.0", "status", "--dir", dir); code != 0 || !strings.Contains(out, "not installed") {
		t.Fatalf("status before: %d %q", code, out)
	}
	if _, errOut, code := runPluginCmd(t, "v1.2.0", "install", "--dir", dir); code != 0 {
		t.Fatalf("install: %d %q", code, errOut)
	}
	script := filepath.Join(dir, pluginName, pluginName+".py")
	info, err := os.Stat(script)
	if err != nil || info.Mode().Perm()&0o111 == 0 {
		t.Fatalf("script not installed executable: %v %v", info, err)
	}
	if v, ok := readBridgeVersion(filepath.Join(dir, pluginName)); !ok || v != "v1.2.0" {
		t.Fatalf("stamped version: %q %v", v, ok)
	}
	if out, _, _ := runPluginCmd(t, "v1.2.0", "status", "--dir="+dir); !strings.Contains(out, "v1.2.0 (matches the binary)") {
		t.Fatalf("status: %q", out)
	}
	if out, _, _ := runPluginCmd(t, "v1.3.0", "status", "--dir", dir); !strings.Contains(out, "v1.2.0, binary is v1.3.0") {
		t.Fatalf("status, older plug-in: %q", out)
	}
	// An older binary refuses to downgrade; a dev build never blocks.
	if _, errOut, code := runPluginCmd(t, "v1.1.0", "install", "--dir", dir); code != 1 || !strings.Contains(errOut, "newer than this binary") {
		t.Fatalf("downgrade: %d %q", code, errOut)
	}
	if _, _, code := runPluginCmd(t, "dev", "install", "--dir", dir); code != 0 {
		t.Fatal("dev install blocked")
	}
	if _, _, code := runPluginCmd(t, "dev", "remove", "--dir", dir); code != 0 {
		t.Fatal("remove failed")
	}
	if _, err := os.Stat(filepath.Join(dir, pluginName)); !os.IsNotExist(err) {
		t.Fatalf("not removed: %v", err)
	}
}

func TestPluginRemoveRefusesForeignFolder(t *testing.T) {
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, pluginName), 0o755)
	os.WriteFile(filepath.Join(dir, pluginName, "other.py"), []byte("x"), 0o644)
	if _, errOut, code := runPluginCmd(t, "dev", "remove", "--dir", dir); code != 1 || !strings.Contains(errOut, "not the mcp-sh-gimp plug-in") {
		t.Fatalf("remove foreign: %d %q", code, errOut)
	}
}

func TestPluginUsage(t *testing.T) {
	for _, args := range [][]string{nil, {"bogus"}, {"install", "--nope"}} {
		if _, _, code := runPluginCmd(t, "dev", args...); code != 2 {
			t.Errorf("%v: exit %d, want 2", args, code)
		}
	}
}
