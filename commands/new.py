# summary: create a new image in a window: new WIDTH HEIGHT [--fill COLOR|transparent]
# usage: new WIDTH HEIGHT [--fill COLOR|transparent]     default fill: white
# Prints the image as JSON (see images); it is unsaved, so commands name it #ID.
args = list(ARGS)
fill = "white"
if "--fill" in args:
    i = args.index("--fill")
    if i + 1 >= len(args):
        fail("--fill needs a color or transparent")
    fill = args[i + 1]
    del args[i:i + 2]
if len(args) != 2 or not all(a.isdigit() and 0 < int(a) <= 524288 for a in args):
    fail("usage: new WIDTH HEIGHT [--fill COLOR|transparent]  (sizes are whole pixels)")
width, height = int(args[0]), int(args[1])
transparent = fill == "transparent"
color = None if transparent else parse_color(fill, "--fill")

img = Gimp.Image.new(width, height, Gimp.ImageBaseType.RGB)
kind = Gimp.ImageType.RGBA_IMAGE if transparent else Gimp.ImageType.RGB_IMAGE
layer = Gimp.Layer.new(img, "Background", width, height, kind, 100, Gimp.LayerMode.NORMAL)
img.insert_layer(layer, None, 0)
if transparent:
    layer.edit_clear()
else:
    Gimp.context_push()  # keep the user's foreground color
    try:
        Gimp.context_set_foreground(color)
        layer.edit_fill(Gimp.FillType.FOREGROUND)
    finally:
        Gimp.context_pop()
img.clean_all()
Gimp.Display.new(img)
Gimp.displays_flush()
emit(image_info(img))
