package main

import (
	"io/fs"
	"strings"
	"testing"

	"github.com/brohd11/agent-shell/profile"
)

func load(t *testing.T) *profile.Loaded {
	t.Helper()
	l, err := profile.Load(profile.App{Name: "gimp", FS: appFS}, profile.Options{ConfigDir: t.TempDir(), ProjectDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	return l
}

func TestConfigLoads(t *testing.T) {
	l := load(t)
	if l.Profile.Title == "" || l.Profile.Setup == "" {
		t.Error("missing title or setup")
	}
	if _, err := l.Sources("test"); err != nil {
		t.Errorf("sources: %v", err)
	}
}

func TestEmbeddedCommands(t *testing.T) {
	entries, err := fs.ReadDir(load(t).CommandDirs[0].FS, ".")
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	for _, e := range entries {
		names = append(names, e.Name())
	}
	if strings.Join(names, ",") != "_lib.py,filter.py,images.py,layer.py,layers.py,new.py,open.py,pdb.py,save.py,view.py" {
		t.Fatalf("embedded commands: %v", names)
	}
}

func TestEmbeddedPlugin(t *testing.T) {
	src := string(pluginSrc)
	if !strings.Contains(src, "Gimp.main(GimpShellBridge.__gtype__") || !bridgeVersion.MatchString(src) {
		t.Fatal("embedded plug-in is not the bridge, or has no BRIDGE_VERSION line")
	}
}
