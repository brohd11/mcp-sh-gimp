# Development

[Back to README](../README.md)

```sh
make           # host build -> build/<os>-<arch>/mcp_sh_gimp
make test
make package   # release archives for every platform
```

After editing the plug-in, `mcp_sh_gimp plugin install` (from a fresh build) and restart GIMP.

The makefile body, installers, workflows and `cliff.toml` are rendered from
[sh-templates](https://github.com/brohd11/sh-templates) by the workspace's `render-go.sh`.
Only the config blocks above `# ---- end config ----` are edited here. Pushing a `v*` tag
releases.
