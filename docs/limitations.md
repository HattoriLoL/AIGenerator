# Limitations

[Back to the README](../README.md)

- **SDXL checkpoints only**, in a single `.safetensors` (or `.ckpt`) file. Pony Diffusion V6 XL is the target; other
  SDXL anime models (for example Illustrious or NoobAI based ones) load the same way, but the `score_*` quality tags
  are Pony's: turn them off (`"quality": false`) for models that were not trained with them.
- **Reproducibility:** the same request with the same seed gives the same image on the same machine and the same
  library versions in most cases, but GPU kernels are not guaranteed to be deterministic, so small differences can
  appear. The image is not guaranteed to match other programs (AUTOMATIC1111, ComfyUI) with the same parameters:
  their noise and prompt handling differ.
- **Prompt syntax:** AUTOMATIC1111 weights (`(tag:1.2)`, `(tag)`, `[tag]`) are supported; `BREAK`, prompt editing
  (`[a:b:10]`) and alternation (`[a|b]`) are not. Inside a tag, a `+` or `-` right after a word is read by compel as a
  weight.
- **Face fix:** the OpenCV cascade finds frontal and near-frontal anime faces; profiles, very small faces and
  non-anime styles are often missed. Nothing happens to an image where no face is found (the report says
  `"found": 0`).
- **Hires fix:** the upscaler model runs on the whole image at once (no tiling); at 2048 px input it needs several
  GB of GPU memory. Use `"upscaler": "lanczos"` or a smaller size if it runs out.
- **No image-to-image or inpaint input** from the user yet: the image-to-image and inpaint pipelines are only used
  inside the hires fix and the face fix.
- **Memory in the report:** the RAM of the `memory` entry is read on Linux and Windows only (null elsewhere).
- **NVIDIA GPUs only** (PyTorch for CUDA 12.8). **Windows is not tested yet**: the launchers and setup were written
  and checked on Linux ([windows.md](windows.md) has the checklist for a first run).
- **One GPU, one generation at a time** in the web interface.
