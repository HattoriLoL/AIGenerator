# Installation and models

[Back to the README](../README.md)

## The environment

Requirements: Linux, an NVIDIA GPU (16 GB is comfortable for SDXL with hires fix; 8 GB may work at 1024 px without
it) and [uv](https://docs.astral.sh/uv/).

```
bin/install.sh
```

It runs `uv sync`, which creates `.venv/` with Python 3.12 (from `.python-version`) and installs the dependencies of
`pyproject.toml`, with PyTorch built for CUDA 12.8 (RTX 50 cards need it; older cards work with it too). It then
creates the model, `characters/` and `output/` folders and prints whether PyTorch sees the GPU. Nothing else is
downloaded.

To use another Python environment, set `AIGEN_PYTHON` to its interpreter: the launchers use it instead of `.venv/`.

## The models

| What | Where (default) | How |
|---|---|---|
| The checkpoint: Pony Diffusion V6 XL, or another SDXL model | anywhere; set its path in `config.local.ini` | download it from the model page (Civitai may ask for an account) |
| LoRAs (optional) | `models/loras/` (subfolders allowed) | `.safetensors` files trained for Pony / SDXL |
| The upscaler for the hires fix | `models/upscalers/RealESRGAN_x4plus_anime_6B.pth` | `bin/download_extras.sh` |
| The face detector for the face fix | `models/detectors/lbpcascade_animeface.xml` | `bin/download_extras.sh` |

`bin/download_extras.sh` downloads the two auxiliary files (both with licenses that allow commercial use; see
[licenses.md](licenses.md)) and skips the ones already there.

The first time a checkpoint is loaded, diffusers downloads the SDXL pipeline configuration files (a few kilobytes,
from Hugging Face) and caches them.

## Configuration

`config.ini` (versioned) is only the template. A machine's paths go in `config.local.ini` (ignored by git), with the
same sections and keys:

```ini
[models]
checkpoint = models/checkpoints/ponyDiffusionV6XL.safetensors
```

Or in environment variables, which win over both files:

| Variable | Key | Default |
|---|---|---|
| `AIGEN_CHECKPOINT` | `[models] checkpoint` | none |
| `AIGEN_VAE` | `[models] vae` | none (the checkpoint's own VAE) |
| `AIGEN_LORAS` | `[models] loras_folder` | `models/loras` |
| `AIGEN_UPSCALER` | `[models] upscaler` | `models/upscalers/RealESRGAN_x4plus_anime_6B.pth` |
| `AIGEN_FACE_DETECTOR` | `[models] face_detector` | `models/detectors/lbpcascade_animeface.xml` |
| `AIGEN_SHEETS` | `[folders] sheets` | `characters` |
| `AIGEN_OUTPUT` | `[folders] output` | `output` (where the web interface writes) |
| `AIGEN_PORT` | `[web] port` | `7860` |

Relative paths are relative to the repository root; `~` is the home folder. `models/`, `characters/` and `output/`
are ignored by git.
