# summary: find and apply any GEGL filter, merged or live: filter ops|info|apply|ls|rm|merge
# usage: filter ops [PATTERN]          filters as JSON lines {name, title, categories}, matching PATTERN
#        filter info OP                OP's details, then one JSON line per parameter
#        filter apply OP [KEY=VALUE...] [--live] [LAYER...]
#        filter ls [LAYER...]          live filters (default: on every layer)
#        filter rm FILTER...           remove live filters (ids, or JSON lines from filter ls)
#        filter merge [LAYER...]       bake a layer's live filters into its pixels
# LAYERs are ids or IMAGE/Group/Layer paths, from arguments or stdin (e.g. from layers).
# apply checks every KEY=VALUE against the filter's parameters (types, ranges, choices)
# before any layer changes, then merges the filter into the pixels, or with --live keeps
# it as an editable filter in GIMP's Layers dock. One undo step per image.
#   filter ops blur
#   filter info gegl:gaussian-blur
#   layers | jq -c 'select(.name == "Sky")' | filter apply gegl:gaussian-blur std-dev-x=8 std-dev-y=8
# GEGL is reached through GIMP's own procedures: calling it directly from the plug-in
# crashes it.
def available():
    return list(pdb_call("gimp-drawable-filter-operation-get-available")[0])


def details(op):
    names, values = pdb_call("gimp-drawable-filter-operation-get-details", operation_name=op)
    return dict(zip(names, values))


def check_op(op):
    ops = available()
    if op not in ops:
        fail("unknown filter %r%s (list them with: filter ops)" % (op, did_you_mean(op, ops)))


def any_drawable():
    for img in Gimp.get_images():
        layers = img.get_layers()
        if layers:
            return layers[0]
    fail("open an image first: filter parameters are read from a filter on a layer")


def specs(op, drawable=None):
    """OP's parameters as {name: (pspec, default)}, read from a filter that is never
    attached to the layer."""
    f = Gimp.DrawableFilter.new(drawable or any_drawable(), op, "")
    try:
        config = f.get_config()
        return {p.name: (p, config.get_property(p.name)) for p in config.list_properties()}
    finally:
        f.delete()


def filter_info(f, layer):
    return {"filter": f.get_id(), "op": f.get_operation_name(), "name": f.get_name(),
            "visible": f.get_visible(), "opacity": num(round(f.get_opacity() * 100, 2)),
            "mode": f.get_blend_mode().value_nick, "id": layer.get_id(), "path": item_path(layer)}


def cmd_ops():
    pattern = " ".join(ARGS[1:]).lower()
    rows = []
    for op in sorted(available()):
        d = details(op)
        row = {"name": op, "title": d.get("title") or "", "categories": d.get("categories") or ""}
        if pattern in " ".join(row.values()).lower():
            rows.append(row)
    for row in rows:
        emit(row)


def cmd_info():
    if len(ARGS) < 2:
        fail("usage: filter info OP")
    op = ARGS[1]
    check_op(op)
    d = details(op)
    params = specs(op)
    emit({"name": op, "title": d.get("title", ""), "description": d.get("description", ""),
          "categories": d.get("categories", "")})
    for pspec, default in params.values():
        emit(describe(pspec, default))


def cmd_apply():
    if len(ARGS) < 2:
        fail("usage: filter apply OP [KEY=VALUE...] [--live] [LAYER...]")
    op = ARGS[1]
    rest = [a for a in ARGS[2:] if a != "--live"]
    live = len(rest) != len(ARGS) - 2
    kv, layer_args = split_kv(rest)
    check_op(op)
    layers = [resolve(r) for r in layer_args] if layer_args else targets(len(ARGS))
    for layer in layers:
        if not isinstance(layer, Gimp.Drawable) or (isinstance(layer, Gimp.Layer) and layer.is_group()):
            fail("%s: filters apply to layers, not %s" % (item_path(layer), "groups" if isinstance(layer, Gimp.Layer) else type(layer).__name__))
    params = specs(op, layers[0])
    values = {}
    for key, text in kv.items():
        if key not in params:
            fail("%s has no parameter %r%s (see: filter info %s)" % (op, key, did_you_mean(key, list(params)), op))
        values[key] = convert(params[key][0], text, key)
    out = []
    with undo_group(images_of(layers)):
        for layer in layers:
            f = Gimp.DrawableFilter.new(layer, op, "")
            config = f.get_config()
            for key, value in values.items():
                set_value(config, params[key][0], value)
            f.update()
            if live:
                layer.append_filter(f)
                out.append(filter_info(f, layer))
            else:
                layer.merge_filter(f)
                out.append({"id": layer.get_id(), "path": item_path(layer)})
    for row in out:
        emit(row)


def all_layers():
    return [layer for img in Gimp.get_images() for layer, _ in walk(img)]


def cmd_ls():
    layers = targets(1, allow_empty=True) or all_layers()
    rows = [filter_info(f, layer) for layer in layers for f in layer.get_filters()]
    for row in rows:
        emit(row)


def cmd_rm():
    # A filter does not know its layer, so look it up among every layer's filters.
    owner = {f.get_id(): (f, layer) for layer in all_layers() for f in layer.get_filters()}
    found, layers = [], []
    for ref in refs(1, field="filter"):
        if not str(ref).isdigit():
            fail("not a filter id: %r (ids come from filter ls)" % ref)
        if int(ref) not in owner:
            fail("no live filter with id %s" % ref)
        f, layer = owner[int(ref)]
        found.append(f)
        layers.append(layer)
    if not found:
        fail("no filters: pass filter ids, or JSON lines from filter ls")
    out = [{"id": layer.get_id(), "path": item_path(layer)} for layer in layers]
    with undo_group(images_of(layers)):
        for f in found:
            f.delete()
    for row in out:
        emit(row)


def cmd_merge():
    layers = [l for l in (targets(1, allow_empty=True) or all_layers()) if l.get_filters()]
    with undo_group(images_of(layers)):
        for layer in layers:
            layer.merge_filters()
    for layer in layers:
        emit({"id": layer.get_id(), "path": item_path(layer)})


COMMANDS = {"ops": cmd_ops, "info": cmd_info, "apply": cmd_apply, "ls": cmd_ls, "rm": cmd_rm, "merge": cmd_merge}
if not ARGS or ARGS[0] not in COMMANDS:
    fail("usage: filter ops|info|apply|ls|rm|merge ... (see: help filter)")
COMMANDS[ARGS[0]]()
