# Third-party licenses

[Back to the README](../README.md)

AIGenerator itself is licensed under the GPL-3.0 ([LICENSE](../LICENSE)). Every dependency in `pyproject.toml` has a row
here (checked by `tests/test_contrato.py`), and only licenses that allow commercial use are accepted.

| Component | License | Use |
|---|---|---|
| torch | BSD-3-Clause | tensors and the GPU (PyTorch) |
| torchvision | BSD-3-Clause | required by spandrel and transformers; installed from the same CUDA index as torch |
| diffusers | Apache-2.0 | the SDXL pipelines (text to image, image to image, inpaint) |
| transformers | Apache-2.0 | the CLIP text encoders |
| accelerate | Apache-2.0 | model loading for diffusers |
| safetensors | Apache-2.0 | reading the model files |
| peft | Apache-2.0 | LoRAs as adapters |
| compel | MIT | prompt weights and long prompts |
| pillow | MIT-CMU (HPND) | images and PNG text chunks |
| numpy | BSD-3-Clause | arrays |
| opencv-python-headless | Apache-2.0 (OpenCV) / MIT (the wheel) | face detection |
| spandrel | MIT | loading the upscaler model |
| gradio | Apache-2.0 | the web interface |

## Models (not in the repository)

The repository contains no model weights: each user downloads them ([instalacao.md](instalacao.md)) and is
responsible for following their licenses.

| Model | License | Use |
|---|---|---|
| Pony Diffusion V6 XL (or another SDXL checkpoint) | a modified Fair AI Public License 1.0-SD, set by its author | the checkpoint; read its license on the model page before using it, in particular for commercial use or for running it as a service |
| RealESRGAN_x4plus_anime_6B | BSD-3-Clause | the default upscaler for the hires fix |
| lbpcascade_animeface | MIT | the default face detector |

Components with research-only or non-commercial licenses are deliberately not the defaults: for example, the
4x-AnimeSharp upscaler (CC BY-NC-SA 4.0) and Ultralytics YOLO face detectors (AGPL-3.0).
