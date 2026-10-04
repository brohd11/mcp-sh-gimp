# summary: set a property on many layers at once: layer set PROP VALUE [LAYER...]
# usage: layer set PROP VALUE [LAYER...]     prints each changed layer as JSON
# LAYERs are ids or IMAGE/Group/Layer paths, from arguments or stdin (e.g. from layers):
#   layers | jq -c 'select(.kind == "text")' | layer set visible false
# PROPs:
#   name TEXT          visible BOOL          opacity 0-100      mode MODE (e.g. multiply, screen)
#   offset X,Y         color_tag TAG (none, blue, green, yellow, orange, brown, red, violet, gray)
#   lock_content BOOL  lock_position BOOL    lock_alpha BOOL    lock_visibility BOOL
# The value is checked before any layer changes; one undo step per image.
SETTERS = {
    "name": "set_name", "visible": "set_visible", "opacity": "set_opacity", "mode": "set_mode",
    "offset": "set_offsets", "color_tag": "set_color_tag", "lock_content": "set_lock_content",
    "lock_position": "set_lock_position", "lock_alpha": "set_lock_alpha",
    "lock_visibility": "set_lock_visibility",
}


def parse(prop, text):
    if prop == "name":
        return [text]
    if prop in ("visible", "lock_content", "lock_position", "lock_alpha", "lock_visibility"):
        return [parse_bool(text, prop)]
    if prop == "opacity":
        try:
            v = float(text)
        except ValueError:
            fail("opacity: %r is not a number" % text)
        if not 0 <= v <= 100:
            fail("opacity: %s is out of range (0 to 100)" % text)
        return [v]
    if prop == "mode":
        return [enum_value(Gimp.LayerMode, text, "mode")]
    if prop == "color_tag":
        return [enum_value(Gimp.ColorTag, text, "color_tag")]
    if prop == "offset":
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            fail("offset: %r is not X,Y in whole pixels" % text)
        return [int(parts[0]), int(parts[1])]


if not ARGS or ARGS[0] != "set":
    fail("usage: layer set PROP VALUE [LAYER...]")
if len(ARGS) < 3:
    fail("usage: layer set PROP VALUE [LAYER...]  (PROPs: %s)" % ", ".join(SETTERS))
prop = ARGS[1].replace("-", "_")
if prop not in SETTERS:
    fail("unknown property %r (PROPs: %s)" % (ARGS[1], ", ".join(SETTERS)))
value = parse(prop, ARGS[2])
layers = targets(3, kind=Gimp.Layer)
if prop == "lock_alpha":
    groups = [l for l in layers if l.is_group()]
    if groups:
        fail("lock_alpha does not apply to groups: %s" % ", ".join(item_path(g) for g in groups))

with undo_group(images_of(layers)):
    for layer in layers:
        getattr(layer, SETTERS[prop])(*value)
for layer in layers:
    emit({"id": layer.get_id(), "path": item_path(layer)})
