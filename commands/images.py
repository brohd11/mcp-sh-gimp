# summary: the open images as JSON lines: id, label, size, mode, file, unsaved changes
# usage: images
#   {"image_id", "image" (file name, or #ID when unsaved), "image_index", "width", "height",
#    "mode" (rgb/gray/indexed), "file", "dirty", "layers"}
# "image" is what other commands take as IMAGE; image_index is the open-image order.
rows = [image_info(img) for img in Gimp.get_images()]
for row in rows:
    emit(row)
