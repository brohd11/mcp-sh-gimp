# summary: save an image to a file, in the format its extension names: save IMAGE PATH
# usage: save IMAGE PATH        IMAGE: #ID or file name (see images); PATH: absolute or ~/...
# .xcf saves every layer and makes PATH the image's file, like Save As. Other formats
# (.png, .jpg, .webp, .tif, .psd, ...) export the visible image and leave the image's
# file alone, like Export As. Prints {"image_id", "image", "path"}.
if len(ARGS) != 2:
    fail("usage: save IMAGE PATH")
img = image_ref(ARGS[0])
f = file_arg(ARGS[1])
folder = os.path.dirname(f.get_path())
if not os.path.isdir(folder):
    fail("no such folder: %s" % folder)
if not os.path.splitext(f.get_path())[1]:
    fail("%s has no extension to pick a format from (.png, .jpg, .xcf, ...)" % f.get_path())
if f.get_path().lower().endswith(".xcf"):
    if not Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, f, None):
        fail("GIMP could not save %s" % f.get_path())
else:
    # Saving would make PATH the image's file; export from a copy instead.
    copy = img.duplicate()
    try:
        copy.undo_disable()
        if not Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, copy, f, None):
            fail("GIMP could not export %s" % f.get_path())
    finally:
        copy.delete()
emit({"image_id": img.get_id(), "image": image_label(img), "path": f.get_path()})
