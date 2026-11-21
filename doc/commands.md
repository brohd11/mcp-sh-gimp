# Commands

[Back to README](../README.md)

Run `mcp_sh_gimp commands` to list commands. From the agent shell, use
`help -s TERM` to search and `<command> --help` for usage.

| Command | Does |
|---|---|
| `images` | list open images as JSON lines: id, label (file name or `#ID`), dimensions, mode, file and unsaved state |
| `open PATH...`, `new W H [--fill COLOR\|transparent]` | open files, or make a new image, each in a window |
| `save IMAGE PATH` | `.xcf` saves the image there (Save As); other formats export the visible image and leave the image's file alone (Export As) |
| `view [IMAGE] [--max N]` | write a PNG preview, including live filters, and print its path |
| `layers [IMAGE...]` | every layer of the open images, including groups: `id`, `path` (`IMAGE/Group/Layer`), `kind` (layer/group/text), visibility, opacity, mode, offsets, size, mask, live filters |
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
