# mcp-sh-gimp

Give an agent a sandboxed bash shell over the running GIMP session through MCP.
The agent gets `run`, `list_commands` and `help`, and combines app commands with
pipes, loops, `jq` and `grep`. Commands run as Python through the bundled GIMP
plugin. Built on [mcp-sh](https://github.com/brohd11/mcp-sh).

## Install

Requires GIMP 3. Start it once before installing the bridge so its config folder exists.

**macOS / Linux (sh)**

```sh
curl -fsSL https://raw.githubusercontent.com/brohd11/mcp-sh-gimp/main/install.sh | sh
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/brohd11/mcp-sh-gimp/main/install.ps1 | iex
```

Follow the installer's PATH instructions, then run in either shell:

```sh
mcp_sh_gimp setup
mcp_sh_gimp plugin install
```

`setup` creates `~/.mcp-sh/gimp/` and prints registration commands for Claude Code
and Codex. Run the appropriate printed command for your client; `setup` does not
register the server itself.

Restart GIMP, then select **Tools > mcp-sh-gimp > Start Bridge**. The bridge runs
until GIMP quits.

## Quickstart

With an image open in GIMP, check the connection and inspect it:

```sh
mcp_sh_gimp commands
mcp_sh_gimp run 'images'
mcp_sh_gimp run 'layers | head -5'
```

In your MCP client, ask the agent to list the open images and inspect their layers.
Use `list_commands` to discover commands and `help` for usage. Commands act on the
open images; see [Commands](doc/commands.md) for editing and filter examples.

## Documentation

- [Commands](doc/commands.md): files, layers, filters and Python.
- [Bridge](doc/bridge.md): settings, plugin updates and troubleshooting.
- [Custom commands](doc/custom-commands.md): add your own Python scripts.
- [Development](doc/development.md): builds, tests and releases.
- [Core configuration](https://github.com/brohd11/mcp-sh/blob/main/doc/configuration.md) and
  [sandbox](https://github.com/brohd11/mcp-sh/blob/main/doc/sandbox.md).
