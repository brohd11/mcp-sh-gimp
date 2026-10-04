# summary: find and run any PDB procedure, plug-ins included: pdb search|info|run
# usage: pdb search TERM            procedures whose name or blurb matches, as JSON lines
#        pdb info PROC              PROC's details, then one JSON line per argument and return value
#        pdb run PROC [KEY=VALUE...] [LAYER...]
# run converts each VALUE to its argument's type (numbers and ranges, booleans, choices and
# enums by name, colors, absolute file paths, images as #ID or file name, items as ids or
# paths, item lists as comma-separated refs) and checks them all before running. It also
# fills arguments left unset: run-mode becomes non-interactive, and LAYERs (arguments, or
# stdin lines from layers) fill a drawables list, a single drawable/layer/item argument,
# and the image. Return values print as one JSON object; with none, the layers print, so
# it chains. One undo step per image.
#   pdb search unsharp
#   pdb info plug-in-blinds
#   layers | jq -c 'select(.name == "Inner")' | pdb run plug-in-blinds num-segments=8
#   pdb run file-png-export image='#2' file=~/out.png
PDB = Gimp.get_pdb()


def proc_type(proc):
    return proc.get_proc_type().value_nick


def lookup(name):
    if not PDB.procedure_exists(name):
        names = PDB.query_procedures("", "", "", "", "", "", "", "")
        fail("unknown procedure %r%s (find one with: pdb search TERM)" % (name, did_you_mean(name, names)))
    return PDB.lookup_procedure(name)


def cmd_search():
    if len(ARGS) < 2:
        fail("usage: pdb search TERM")
    term = "(?i)" + re.escape(" ".join(ARGS[1:]))
    names = set(PDB.query_procedures(term, "", "", "", "", "", "", ""))
    names |= set(PDB.query_procedures("", term, "", "", "", "", "", ""))
    rows = []
    for name in sorted(names):
        proc = PDB.lookup_procedure(name)
        rows.append({"name": name, "type": proc_type(proc), "blurb": proc.get_blurb() or ""})
    for row in rows:
        emit(row)


def cmd_info():
    if len(ARGS) < 2:
        fail("usage: pdb info PROC")
    proc = lookup(ARGS[1])
    rows = [{"name": proc.get_name(), "type": proc_type(proc), "blurb": proc.get_blurb() or "",
             "help": proc.get_help() or "", "menu_paths": list(proc.get_menu_paths())}]
    rows += [describe(p) for p in proc.get_arguments()]
    for p in proc.get_return_values():
        d = describe(p)
        d["returns"] = d.pop("param")
        rows.append(d)
    for row in rows:
        emit(row)


def is_item_arg(pspec):
    return pspec.value_type.is_a(Gimp.Item.__gtype__)


def cmd_run():
    if len(ARGS) < 2:
        fail("usage: pdb run PROC [KEY=VALUE...] [LAYER...]")
    proc = lookup(ARGS[1])
    args = {p.name: p for p in proc.get_arguments()}
    kv, rest = split_kv(ARGS[2:])
    layers = [resolve(r) for r in rest] if rest else targets(len(ARGS), allow_empty=True)
    values = {}
    for key, text in kv.items():
        if key not in args:
            fail("%s has no argument %r%s (see: pdb info %s)" % (proc.get_name(), key, did_you_mean(key, list(args)), proc.get_name()))
        values[key] = convert(args[key], text, key)

    if "run-mode" in args and "run-mode" not in values:
        values["run-mode"] = Gimp.RunMode.NONINTERACTIVE
    if layers:
        used = False
        arrays = [n for n, p in args.items() if type_name(p) == "items" and n not in values]
        singles = [n for n, p in args.items() if is_item_arg(p) and n not in values]
        if arrays:
            values[arrays[0]] = layers
            used = True
        elif singles:
            if len(layers) > 1:
                fail("%s takes one %s; got %d layers" % (proc.get_name(), singles[0], len(layers)))
            values[singles[0]] = convert(args[singles[0]], str(layers[0].get_id()), singles[0])
            used = True
        images = images_of(layers)
        image_args = [n for n, p in args.items() if type_name(p) == "image" and n not in values]
        if image_args:
            if len(images) > 1:
                fail("%s takes one image; the layers come from %d" % (proc.get_name(), len(images)))
            values[image_args[0]] = images[0]
            used = True
        if not used:
            fail("%s has no unset image or drawable argument to take the layers" % proc.get_name())

    touched = []
    for v in values.values():
        for x in (v if isinstance(v, list) else [v]):
            img = x if isinstance(x, Gimp.Image) else x.get_image() if isinstance(x, Gimp.Item) else None
            if img is not None and img not in touched:
                touched.append(img)
    config = proc.create_config()
    for key, value in values.items():
        set_value(config, args[key], value)
    with undo_group(touched):
        results = run_procedure(proc, config)
    out = {p.name: to_json(v) for p, v in zip(proc.get_return_values(), results)}
    if out:
        emit(out)
    else:
        for layer in layers:
            emit({"id": layer.get_id(), "path": item_path(layer)})


COMMANDS = {"search": cmd_search, "info": cmd_info, "run": cmd_run}
if not ARGS or ARGS[0] not in COMMANDS:
    fail("usage: pdb search|info|run ... (see: help pdb)")
COMMANDS[ARGS[0]]()
