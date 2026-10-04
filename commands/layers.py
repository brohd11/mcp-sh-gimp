# summary: every layer of the open images, inside groups too, as JSON lines with an id and path
# usage: layers [IMAGE...]      IMAGE: #ID or file name; default: every open image
# One JSON object per layer, top to bottom, groups before their contents:
#   {"id", "path", "image", "image_id", "image_index", "name", "kind" (layer/group/text),
#    "parent", "visible", "opacity", "mode", "x", "y", "width", "height", "mask", "filters"}
# Paths are IMAGE/Group/Layer; unsaved images are #ID. Pipe into commands that take
# layers, or pick with jq first:
#   layers | jq -c 'select(.kind == "text")' | layer set visible false
# image_index is the index gimp-mcp's tools take (--image_index).
images = [image_ref(a) for a in ARGS] or list(Gimp.get_images())
rows = [layer_info(layer, path) for img in images for layer, path in walk(img)]
for row in rows:
    emit(row)
