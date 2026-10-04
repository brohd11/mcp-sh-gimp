# Shared helpers for gimp-shell's script commands, defined before every Python command.
# A user commands/_lib.py is appended after this one and can add or replace helpers.
#
# Commands run in the bridge plug-in's process, one at a time, each in a fresh namespace.
# They check everything first, then change things, then print, so a failure never leaves
# half an edit behind. A native crash takes the bridge down (and can leave GIMP partly
# unresponsive), so commands never call GEGL directly: it crashes the plug-in.
import difflib
import json
import os
import re
from contextlib import contextmanager

from gi.repository import Gegl, Gimp, Gio, GObject


class Fail(Exception):
    """An error shown to the agent as its plain message."""


def fail(msg):
    raise Fail(msg)


def emit(obj):
    print(json.dumps(obj))


# ---- images and layers ----------------------------------------------------------------


def image_label(image):
    """A file image's file name, or #ID for an unsaved one."""
    f = image.get_file()
    return os.path.basename(f.get_path()) if f and f.get_path() else "#%d" % image.get_id()


def image_ref(ref):
    """The open image named by #ID, a bare ID, or its file name."""
    ref = ref.strip()
    images = Gimp.get_images()
    digits = ref[1:] if ref.startswith("#") else ref
    if digits.isdigit():
        img = Gimp.Image.get_by_id(int(digits))
        if img is None or not img.is_valid():
            fail("no open image with id %s (open: %s)" % (digits, open_images(images)))
        return img
    found = [i for i in images if image_label(i) == ref]
    if not found:
        fail("no open image named %r (open: %s)" % (ref, open_images(images)))
    if len(found) > 1:
        fail("%d open images are named %r: use #ID (open: %s)" % (len(found), ref, open_images(images)))
    return found[0]


def open_images(images=None):
    images = Gimp.get_images() if images is None else images
    labels = []
    for i in images:
        label = image_label(i)
        labels.append(label if label.startswith("#") else "#%d %s" % (i.get_id(), label))
    return ", ".join(labels) or "none"


def image_info(image):
    f = image.get_file()
    return {
        "image_id": image.get_id(),
        "image": image_label(image),
        "image_index": Gimp.get_images().index(image),
        "width": image.get_width(), "height": image.get_height(),
        "mode": image.get_base_type().value_nick,
        "file": f.get_path() if f else None,
        "dirty": image.is_dirty(),
        "layers": sum(1 for _ in walk(image)),
    }


def file_arg(text, what="path"):
    """An absolute (or ~/...) path as a Gio.File."""
    path = os.path.expanduser(text)
    if not os.path.isabs(path):
        fail("%s: use an absolute path (or ~/...), not %r" % (what, text))
    return Gio.File.new_for_path(path)


def children(layer_or_image):
    if isinstance(layer_or_image, Gimp.Image):
        return list(layer_or_image.get_layers())
    return list(layer_or_image.get_children()) if layer_or_image.is_group() else []


def walk(image):
    """Every layer of image, top to bottom, entering groups, as (layer, path)."""
    def rec(parent, prefix):
        for layer in children(parent):
            path = prefix + "/" + layer.get_name()
            yield layer, path
            yield from rec(layer, path)
    yield from rec(image, image_label(image))


def item_path(item):
    names = []
    cur = item
    while cur is not None:
        names.append(cur.get_name())
        cur = cur.get_parent()
    return image_label(item.get_image()) + "/" + "/".join(reversed(names))


def layer_kind(layer):
    if layer.is_group():
        return "group"
    if layer.is_text_layer():
        return "text"
    return "layer"


def layer_info(layer, path=None):
    image = layer.get_image()
    _, x, y = layer.get_offsets()
    parent = layer.get_parent()
    return {
        "id": layer.get_id(),
        "path": path or item_path(layer),
        "image": image_label(image),
        "image_id": image.get_id(),
        "image_index": Gimp.get_images().index(image),
        "name": layer.get_name(),
        "kind": layer_kind(layer),
        "parent": parent.get_id() if parent else None,
        "visible": layer.get_visible(),
        "opacity": num(round(layer.get_opacity(), 2)),
        "mode": layer.get_mode().value_nick,
        "x": x, "y": y,
        "width": layer.get_width(), "height": layer.get_height(),
        "mask": layer.get_mask() is not None,
        "filters": len(layer.get_filters()),
    }


def resolve(ref):
    """The item named by an id or an IMAGE/Group/Layer path."""
    ref = str(ref).strip()
    if ref.isdigit():
        item = Gimp.Item.get_by_id(int(ref))
        if item is None or not item.is_valid():
            fail("no item with id %s" % ref)
        return item
    if "/" not in ref:
        fail("not an item id or IMAGE/LAYER path: %r" % ref)
    head, rest = ref.split("/", 1)
    cur = image_ref(head)
    for name in rest.split("/"):
        found = [c for c in children(cur) if c.get_name() == name]
        if not found:
            where = image_label(cur) if isinstance(cur, Gimp.Image) else item_path(cur)
            fail("not found: %s (no %r in %s)" % (ref, name, where))
        if len(found) > 1:
            fail("%d layers are named %r in %s: use the id" % (len(found), name, ref))
        cur = found[0]
    if isinstance(cur, Gimp.Image):
        fail("%r is an image, not a layer" % ref)
    return cur


def refs(first=0, field="id"):
    """Refs from ARGS[first:], or else one per STDIN line: plain refs, or JSON objects
    with `field` (or "path")."""
    out = list(ARGS[first:])
    if out:
        return out
    for line in STDIN.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                fail("stdin: not a JSON object: " + line)
            ref = obj.get(field, obj.get("path"))
            if ref is None:
                fail("stdin: JSON line has no %s or path field: %s" % (field, line))
            line = str(ref)
        out.append(line)
    return out


def targets(first=0, allow_empty=False, kind=Gimp.Drawable):
    """Items named by ARGS[first:] or STDIN, checked to be `kind`."""
    items = []
    for ref in refs(first):
        item = resolve(ref)
        if not isinstance(item, kind):
            fail("%s is a %s, not a %s" % (item_path(item), type(item).__name__, kind.__name__))
        if item not in items:
            items.append(item)
    if not items and not allow_empty:
        fail("no targets: pass ids or paths as arguments, or one per stdin line (e.g. from layers)")
    return items


def images_of(items):
    out = []
    for item in items:
        img = item.get_image()
        if img not in out:
            out.append(img)
    return out


@contextmanager
def undo_group(images):
    """One undo step per image for everything inside."""
    for img in images:
        img.undo_group_start()
    try:
        yield
    finally:
        for img in images:
            img.undo_group_end()
        Gimp.displays_flush()


# ---- procedures ------------------------------------------------------------------------


def run_procedure(proc, config):
    """Run a PDB procedure; its return values as a list, or a Fail with GIMP's message."""
    res = proc.run(config)
    if res.index(0) != Gimp.PDBStatusType.SUCCESS:
        msg = res.index(1) if res.length() > 1 and isinstance(res.index(1), str) else res.index(0).value_nick
        fail("%s: %s" % (proc.get_name(), msg))
    out = []
    for i, pspec in enumerate(proc.get_return_values(), 1):
        # Item arrays come back boxed; only this getter unpacks them.
        out.append(res.get_core_object_array(i) if type_name(pspec) == "items" else plain(res.index(i)))
    return out


def plain(v):
    """v with value arrays copied into lists. A value array inside a result is only valid
    while the result is, so it must be copied before the result is dropped."""
    if isinstance(v, Gimp.ValueArray):
        return [plain(v.index(i)) for i in range(v.length())]
    return v


def pdb_call(name, **args):
    """Run a PDB procedure with Python values (keyword names use _ for -)."""
    proc = Gimp.get_pdb().lookup_procedure(name)
    config = proc.create_config()
    for k, v in args.items():
        config.set_property(k.replace("_", "-"), v)
    return run_procedure(proc, config)


# ---- values ---------------------------------------------------------------------------


def split_kv(tokens):
    """KEY=VALUE tokens as a dict (in order), and the other tokens."""
    kv, rest = {}, []
    for t in tokens:
        if "=" in t and not t.startswith("=") and "/" not in t.split("=", 1)[0]:
            k, v = t.split("=", 1)
            kv[k.replace("_", "-")] = v
        else:
            rest.append(t)
    return kv, rest


def type_name(pspec):
    vt = pspec.value_type
    if is_choice(pspec):
        return "choice"
    if vt.name == "GimpCoreObjectArray":
        return "items"
    for t, name in ((GObject.TYPE_BOOLEAN, "bool"), (GObject.TYPE_STRING, "string")):
        if vt == t:
            return name
    if vt.name in ("gint", "guint", "glong", "gulong", "gint64", "guint64", "guchar", "gchar"):
        return "int"
    if vt.name in ("gdouble", "gfloat"):
        return "number"
    if vt.is_a(GObject.TYPE_ENUM):
        return "enum"
    if vt.name == "GeglColor":
        return "color"
    if vt.name == "GFile":
        return "file"
    if vt.is_a(Gimp.Image.__gtype__):
        return "image"
    if vt.is_a(Gimp.Item.__gtype__):
        return vt.pytype.__name__.lower()
    return vt.name


def is_choice(pspec):
    return type(pspec).__name__ == "ParamChoice"


def choices(pspec):
    if is_choice(pspec):
        return list(Gimp.param_spec_choice_get_choice(pspec).list_nicks())
    if pspec.value_type.is_a(GObject.TYPE_ENUM):
        return [v.value_nick for v in pspec.value_type.pytype.__enum_values__.values()]
    return None


def enum_value(enum_type, text, what):
    values = enum_type.__enum_values__.values()
    key = text.strip().lower().replace("_", "-")
    for v in values:
        if key in (v.value_nick, v.value_name.lower().replace("_", "-")):
            return v
    if key.lstrip("-").isdigit():
        for v in values:
            if int(v) == int(key):
                return v
    nicks = [v.value_nick for v in values if not v.value_nick.endswith("-legacy")]
    fail("%s: %r is not one of %s%s" % (what, text, ", ".join(nicks), did_you_mean(key, nicks)))


def did_you_mean(text, options):
    close = difflib.get_close_matches(text, options, n=1)
    return " (did you mean %s?)" % close[0] if close else ""


_TRUE = ("true", "1", "yes", "on")
_FALSE = ("false", "0", "no", "off")


def parse_bool(text, what):
    t = text.strip().lower()
    if t in _TRUE:
        return True
    if t in _FALSE:
        return False
    fail("%s: %r is not a boolean (true/false)" % (what, text))


def parse_color(text, what):
    t = text.strip()
    color = Gegl.Color.new(t)
    # Gegl turns anything it cannot parse into its parse-error color: cyan at 67% alpha.
    if [round(c, 2) for c in color.get_rgba()] == [0.0, 1.0, 1.0, 0.67]:
        fail("%s: %r is not a color (names, #rrggbb, #rrggbbaa, rgb(...), rgba(...))" % (what, text))
    return color


def convert(pspec, text, what=None):
    """text as a value for pspec: type converted and range checked, or a Fail. GLib
    would otherwise ignore a bad value and keep the default without a word."""
    what = what or pspec.name
    kind = type_name(pspec)
    if kind == "choice":
        nicks = choices(pspec)
        if text not in nicks:
            fail("%s: %r is not one of %s%s" % (what, text, ", ".join(nicks), did_you_mean(text, nicks)))
        return text
    if kind == "bool":
        return parse_bool(text, what)
    if kind in ("int", "number"):
        try:
            v = int(text) if kind == "int" else float(text)
        except ValueError:
            fail("%s: %r is not %s" % (what, text, "an integer" if kind == "int" else "a number"))
        lo, hi = getattr(pspec, "minimum", None), getattr(pspec, "maximum", None)
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            fail("%s: %s is out of range (%s to %s)" % (what, text, num(lo), num(hi)))
        return v
    if kind == "string":
        return text
    if kind == "enum":
        return enum_value(pspec.value_type.pytype, text, what)
    if kind == "color":
        return parse_color(text, what)
    if kind == "file":
        return file_arg(text, what)
    if kind == "image":
        return image_ref(text)
    if kind == "items":
        return [resolve(r) for r in text.split(",") if r.strip()]
    if pspec.value_type.is_a(Gimp.Item.__gtype__):
        item = resolve(text)
        if not isinstance(item, pspec.value_type.pytype):
            fail("%s: %s is a %s, not a %s" % (what, item_path(item), type(item).__name__, kind))
        return item
    fail("%s: values of type %s are not supported here; use gimp call_api" % (what, pspec.value_type.name))


def set_value(config, pspec, value):
    if type_name(pspec) == "items":
        config.set_core_object_array(pspec.name, value)
    else:
        config.set_property(pspec.name, value)


def num(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def describe(pspec, default=None):
    """A parameter as JSON: name, type, default, range, choices, description."""
    d = {"param": pspec.name, "type": type_name(pspec)}
    if default is None:
        default = getattr(pspec, "default_value", None)
        if isinstance(default, int) and type_name(pspec) == "enum":
            default = pspec.value_type.pytype(default)
    if default is not None:
        d["default"] = to_json(default)
    lo, hi = getattr(pspec, "minimum", None), getattr(pspec, "maximum", None)
    if type_name(pspec) in ("int", "number") and lo is not None:
        d["min"], d["max"] = num(lo), num(hi)
    ch = choices(pspec)
    if ch:
        d["choices"] = ch
    blurb = pspec.get_blurb()
    if blurb and blurb != pspec.name:
        d["description"] = blurb
    return d


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_json(v):
    # Enums first: they are ints too.
    if isinstance(v, (GObject.GEnum, GObject.GFlags)):
        return v.value_nick
    if v is None or isinstance(v, (bool, int, float, str)):
        return num(v) if isinstance(v, float) else v
    if isinstance(v, Gimp.Item):
        return {"id": v.get_id(), "path": item_path(v)}
    if isinstance(v, Gimp.Image):
        return {"image_id": v.get_id(), "image": image_label(v)}
    if isinstance(v, Gio.File):
        return v.get_path() or v.get_uri()
    if isinstance(v, Gegl.Color):
        r, g, b, a = v.get_rgba()
        out = "#" + "".join("%02x" % round(_srgb(c) * 255) for c in (r, g, b))
        return out if a >= 1 else out + "%02x" % round(max(0.0, min(1.0, a)) * 255)
    if isinstance(v, (list, tuple)):
        return [to_json(x) for x in v]
    return str(v)
