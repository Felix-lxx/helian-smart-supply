# Vendored YOLOv5 source

`yolov5/` is copied from the project's existing local checkout of `ultralytics/yolov5`, at commit:

`70b964b6d5067fff621f724c85d0e39e6b4c8e4e`

This public source snapshot omits upstream Git metadata, GitHub workflows, sample binary media, model weights, training runs and datasets. The original third-party source files and [AGPL-3.0 license](yolov5/LICENSE) are retained. It is not a Git submodule and requires no recursive clone.

The application loads this local source only when optional PyTorch dependencies and a user-supplied compatible `code/system/best.pt` weight file are available. No model download is performed by the application loader.
