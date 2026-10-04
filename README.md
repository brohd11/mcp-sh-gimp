# gimp-shell

A sandboxed bash shell over the running GIMP session, served over MCP. Built on
[agent-shell](https://github.com/brohd11/agent-shell): the agent gets `run`,
`list_commands` and `help`, and its commands run as Python inside GIMP 3, through a small
plug-in that ships with gimp-shell.

```sh
gimp-shell run 'layers | jq -c "select(.kind == \"text\")" | layer set visible false'
gimp-shell run 'filter ops blur'
gimp-shell run 'layers "#2" | head -1 | filter apply gegl:gaussian-blur std-dev-x=8 std-dev-y=8'
gimp-shell run 'view "#2"'      # prints the path of a PNG of the image
```

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/brohd11/gimp-shell/main/install.sh | sh
gimp-shell setup            # ~/.agent-shell/gimp/ + `claude mcp add -s user gimp-shell -- <path>`
gimp-shell plugin install   # the bridge plug-in, into GIMP's newest 3.x plug-ins folder
```

On Windows: `irm https://raw.githubusercontent.com/brohd11/gimp-shell/main/install.ps1 | iex`.

Start GIMP once before `plugin install`, so its config folder exists (or pass
`--dir PLUGINS_DIR`, from Edit > Preferences > Folders > Plug-ins). Then restart GIMP and
start the bridge from **Tools > gimp-shell > Start Bridge**; it runs until GIMP quits.
`gimp-shell commands` checks the connection, and `gimp-shell plugin status` whether the
installed plug-in matches the binary (after an update: `plugin install` again, then restart
GIMP).

The bridge listens on `127.0.0.1:9520` with no token. To change either, put
`{"port": 9521, "token": "..."}` in `~/.agent-shell/gimp/bridge.json` for the plug-in, and
set `GIMP_SHELL_PORT` / `GIMP_SHELL_TOKEN` for gimp-shell.

## Commands

| Command | Does |
|---|---|
| `images` | the open images as JSON lines: id, label (file name, or `#ID` when unsaved), size, mode, file, unsaved changes |
| `open PATH...`, `new W H [--fill COLOR\|transparent]` | open files, or make a new image, each in a window |
| `save IMAGE PATH` | `.xcf` saves the image there (Save As); other formats export the visible image and leave the image's file alone (Export As) |
| `view [IMAGE] [--max N]` | save a PNG of what the image looks like, live filters included, and print its path, so the agent can look at it |
| `layers [IMAGE...]` | every layer of the open images, **inside groups too**: `id`, `path` (`IMAGE/Group/Layer`), `kind` (layer/group/text), visibility, opacity, mode, offsets, size, mask, live filters |
| `layer set PROP VALUE [LAYER...]` | set `name`, `visible`, `opacity`, `mode`, `offset`, `color_tag` or a lock on many layers at once |
| `filter ops [PATTERN]`, `filter info OP` | find any of GIMP's ~180 GEGL filters by name, title or category, and see a filter's parameters with types, defaults, ranges and choices |
| `filter apply OP [KEY=VALUE...] [--live] [LAYER...]` | apply a filter, merged into the pixels or, with `--live`, kept as an editable filter |
| `filter ls`, `filter rm`, `filter merge` | list, remove or bake in live filters |
| `pdb search TERM`, `pdb info PROC` | find any of GIMP's ~1000 PDB procedures (plug-ins, Script-Fu, file formats) and see its arguments and return values |
| `pdb run PROC [KEY=VALUE...] [LAYER...]` | run one, with each value converted to its argument's type: scaling, cropping, selections, drawing and everything else without its own command |
| `python [ARGS...] < CODE` | run one-off Python inside GIMP (`Gimp`, `Gegl`, `Gio`, `GLib`, `GObject` imported) |

Commands that take layers read ids or paths from arguments, or one per stdin line (JSON
lines with an `id` or `path` work too), and print the layers they changed, so they chain:

```sh
layers | jq -c 'select(.kind == "text")' | layer set opacity 50 | layer set color_tag red
layers | jq -c 'select(.name == "Sky")' | pdb run plug-in-blinds num-segments=8
pdb run gimp-image-get-layers image='#2' | jq -c '.layers[]' | filter apply gegl:pixelize size-x=8 size-y=8
pdb run gimp-image-scale image='#2' new-width=800 new-height=600
```

Values are checked before anything changes: unknown parameters, out-of-range numbers and
invalid choices or colors fail with the valid options, where GLib would silently keep a
default. Each command is one undo step per image (undo in GIMP). `pdb run` sets `run-mode`
to non-interactive and fills a procedure's drawables, drawable and image arguments from the
layers it is given.

## The bridge

`plugin/gimp-shell-bridge/gimp-shell-bridge.py` is a GIMP 3 plug-in speaking agent-shell's
host protocol. It offers one host command, `python`, which runs the code it gets on stdin;
gimp-shell's script commands run through it (`host.exec` in `config.json`). Code runs on the
plug-in's main thread, where libgimp may be called, each run in a fresh namespace. A failure
keeps what was printed before it, and PDB errors go back to the code that called them
instead of GIMP's error console.

Everything runs in the bridge's one process. A native crash there stops the bridge and can
leave GIMP partly unresponsive: restart GIMP, then start the bridge again. Calling GEGL
directly (`Gegl.list_operations()`) crashes it, so the `filter` commands use GIMP's own
procedures instead.

## Your own commands

Keep your own Python commands in a folder of their own and add it:

```sh
gimp-shell commands add ~/code/gimp-tools
```

A `_lib.py` in that folder is appended to the built-in one, so your commands can use and
replace its helpers (`targets`, `resolve`, `layer_info`, `image_ref`, `convert`,
`undo_group`, `pdb_call`, ...). Check before changing anything and print last, as the
built-in commands do. See the agent-shell README for the script format and folder order.

## Development

```sh
make           # host build -> build/<os>-<arch>/gimp-shell
make test
make package   # release archives for every platform
```

After editing the plug-in, `gimp-shell plugin install` (from a fresh build) and restart GIMP.

The makefile body, installers, workflows and `cliff.toml` are rendered from
[sh-templates](https://github.com/brohd11/sh-templates) by the workspace's `render-go.sh`.
Only the config blocks above `# ---- end config ----` are edited here. Pushing a `v*` tag
releases.
