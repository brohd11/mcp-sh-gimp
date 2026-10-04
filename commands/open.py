# summary: open image files in GIMP, each in a window: open PATH...
# usage: open PATH...       absolute paths (or ~/...); prints each image as JSON (see images)
# Any format GIMP reads: xcf, png, jpg, tiff, psd, webp, ...
files = [file_arg(a) for a in ARGS]
if not files:
    fail("usage: open PATH...")
for f in files:
    if not os.path.isfile(f.get_path()):
        fail("no such file: %s" % f.get_path())
opened = []
for f in files:
    img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, f)
    if img is None:
        fail("GIMP could not open %s" % f.get_path())
    Gimp.Display.new(img)
    opened.append(img)
Gimp.displays_flush()
for img in opened:
    emit(image_info(img))
