# summary: save a PNG of what an image looks like and print its path: view [IMAGE] [--max N]
# usage: view [IMAGE] [--max N]     IMAGE: #ID or file name (default: the only open image)
# The visible layers, live filters included, scaled to fit N pixels (default 1024), saved
# under ~/.agent-shell/gimp/images/ (the newest 50 are kept). Open the path to look at it.
import time

args = list(ARGS)
size = 1024
if "--max" in args:
    i = args.index("--max")
    if i + 1 >= len(args) or not args[i + 1].isdigit() or int(args[i + 1]) < 1:
        fail("--max needs a size in pixels")
    size = int(args[i + 1])
    del args[i:i + 2]
if len(args) > 1:
    fail("usage: view [IMAGE] [--max N]")
if args:
    img = image_ref(args[0])
else:
    images = Gimp.get_images()
    if len(images) != 1:
        fail("%s: name one (open: %s)" % ("no image is open" if not images else "%d images are open" % len(images), open_images(images)))
    img = images[0]

folder = os.path.join(os.path.expanduser("~"), ".agent-shell", "gimp", "images")
os.makedirs(folder, exist_ok=True)
path = os.path.join(folder, "view-%s-%s.png" % (img.get_id(), time.strftime("%Y%m%d-%H%M%S")))
copy = img.duplicate()
try:
    copy.undo_disable()
    copy.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
    w, h = copy.get_width(), copy.get_height()
    scale = min(1.0, size / max(w, h))
    if scale < 1.0:
        copy.scale(max(1, round(w * scale)), max(1, round(h * scale)))
    if not Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, copy, Gio.File.new_for_path(path), None):
        fail("GIMP could not save the view")
finally:
    copy.delete()

files = sorted((os.path.join(folder, n) for n in os.listdir(folder)), key=os.path.getmtime, reverse=True)
for old in files[50:]:
    os.remove(old)
print(path)
