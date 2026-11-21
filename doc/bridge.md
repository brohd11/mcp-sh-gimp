# Bridge

[Back to README](../README.md)

## Settings

The bridge listens on `127.0.0.1:9520` with no token by default. To change the port
or add a token, write `~/.mcp-sh/gimp/bridge.json`:

```json
{"port": 9521, "token": "your-token"}
```

Set `MCP_SH_GIMP_PORT` and `MCP_SH_GIMP_TOKEN` to matching values in the
shell binary's environment, including its MCP client registration.

Restart GIMP and start the bridge again after changing its settings.

## Plugin maintenance

```sh
mcp_sh_gimp plugin status
mcp_sh_gimp update
mcp_sh_gimp plugin install
```

`plugin status` compares the installed plugin with the binary. After updating,
reinstall the plugin and restart GIMP, then start the bridge from the Tools menu.
Use `plugin remove` to uninstall it.

If automatic folder detection fails, use `plugin install --dir PLUGINS_DIR`. Find the plugins folder under **Edit > Preferences > Folders > Plug-ins**.

## Connection problems

Run `mcp_sh_gimp commands` to check connectivity. If the bridge is unavailable,
check that the plugin is installed and the bridge is started from the Tools menu,
then verify the port and token match on both sides.

## Implementation

`plugin/mcp-sh-gimp-bridge/mcp-sh-gimp-bridge.py` is a GIMP 3 plugin speaking the core
[host protocol](https://github.com/brohd11/mcp-sh/blob/main/doc/native-hosts.md).
Its `python` command executes stdin; `host.exec` routes script commands through it.

Code runs on the plugin's main thread, with a fresh namespace for each run. Errors
preserve printed output, and PDB errors return to the caller instead of GIMP's console.

A native crash stops the bridge and can leave GIMP partly unresponsive. Restart GIMP
and start the bridge again. Calling `Gegl.list_operations()` directly crashes the
bridge, so the filter commands use GIMP's procedures instead.
