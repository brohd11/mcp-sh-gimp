// gimp-shell: a sandboxed bash shell over GIMP, served over MCP.
// See `gimp-shell --help` and the README.
package main

import (
	"embed"

	"github.com/brohd11/agent-shell"
)

// appFS is the built-in config layer. Directory embeds skip files starting with "_",
// so the command library is listed explicitly.
//
//go:embed config.json commands commands/_lib.py
var appFS embed.FS

// version is set at build time via -ldflags "-X main.version=...". See the Makefile.
var version = "dev"

func main() {
	agentshell.Main(agentshell.Config{
		Name:        "gimp-shell",
		App:         "gimp",
		Version:     version,
		UpdateRepo:  "brohd11/gimp-shell",
		FS:          appFS,
		Subcommands: []agentshell.Subcommand{pluginCommand(version)},
	})
}
