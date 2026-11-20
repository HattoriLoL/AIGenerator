# Installation and models

[Back to the README](../README.md)

## The environment

Requirements: Linux, an NVIDIA GPU (16 GB is comfortable for SDXL with hires fix; 8 GB may work at 1024 px without
it) and [uv](https://docs.astral.sh/uv/).

```
bin/instalar.sh
```

It runs `uv sync`, which creates `.venv/` with Python 3.12 (from `.python-version`) and installs the dependencies of
`pyproject.toml`, with PyTorch built for CUDA 12.8 (RTX 50 cards need it; older cards work with it too). It then
creates the model folders and prints whether PyTorch sees the GPU. Nothing else is downloaded.

To use another Python environment, set `AIGEN_PYTHON` to its interpreter: the launchers use it instead of `.venv/`.

## The models

| What | Where (default) | How |
|---|---|---|
| The checkpoint: Pony Diffusion V6 XL, or another SDXL model | anywhere; set its path in `config.local.ini` | download it from the model page (Civitai may ask for an account) |
| LoRAs (optional) | `models/loras/` (subfolders allowed) | `.safetensors` files trained for Pony / SDXL |
| The upscaler for the hires fix | `models/upscalers/RealESRGAN_x4plus_anime_6B.pth` | `bin/baixar_auxiliares.sh` |
| The face detector for the face fix | `models/detectors/lbpcascade_animeface.xml` | `bin/baixar_auxiliares.sh` |

`bin/baixar_auxiliares.sh` downloads the two auxiliary files (both with licenses that allow commercial use; see
[licencas.md](licencas.md)) and skips the ones already there.

The first time a checkpoint is loaded, diffusers downloads the SDXL pipeline configuration files (a few kilobytes,
from Hugging Face) and caches them.

## Configuration

`config.ini` (versioned) is only the template. A machine's paths go in `config.local.ini` (ignored by git), with the
same sections and keys:

```ini
[modelos]
checkpoint = models/checkpoints/ponyDiffusionV6XL.safetensors
```

Or in environment variables, which win over both files:

| Variable | Key | Default |
|---|---|---|
| `AIGEN_CHECKPOINT` | `[modelos] checkpoint` | none |
| `AIGEN_VAE` | `[modelos] vae` | none (the checkpoint's own VAE) |
| `AIGEN_LORAS` | `[modelos] pasta_loras` | `models/loras` |
| `AIGEN_UPSCALER` | `[modelos] upscaler` | `models/upscalers/RealESRGAN_x4plus_anime_6B.pth` |
| `AIGEN_DETECTOR_ROSTO` | `[modelos] detector_rosto` | `models/detectors/lbpcascade_animeface.xml` |
| `AIGEN_FICHAS` | `[pastas] fichas` | `personagens` |
| `AIGEN_SAIDA` | `[pastas] saida` | `saida` (where the web interface writes) |
| `AIGEN_PORTA` | `[web] porta` | `7860` |

Relative paths are relative to the repository root; `~` is the home folder. `models/`, `personagens/` and `saida/`
are ignored by git.
