# Installation and models

[Back to the README](../README.md)

## Requirements

- **An NVIDIA GPU** with its driver installed (16 GB is comfortable for SDXL with hires fix; 8 GB may work at 1024 px
  without it). AIGenerator runs on PyTorch for CUDA 12.8 (RTX 50 cards need it; older cards work with it too); AMD,
  Intel and Apple GPUs are not supported.
- **Linux or Windows 10/11** (64-bit). Windows is not tested yet: see [windows.md](windows.md).
- **About 20 GB of free disk space**: the environment (Python and PyTorch with CUDA, about 7 GB on Linux, plus uv's
  download cache), the checkpoint (6.9 GB) and room for the outputs.
- An internet connection for the first run. Nothing else: setup installs [uv](https://docs.astral.sh/uv/), which
  brings Python 3.12.

## Setup: one command

| System | Command |
|---|---|
| Linux | `./setup.sh` in the repository folder |
| Windows | double-click `setup.bat` (or run it in a Command Prompt) |

It is safe to run again, at any time (after a `git pull`, or when a step failed): what is already done is skipped and
**your files are never overwritten**. The steps:

1. **The GPU check.** `nvidia-smi` must answer; without it, setup stops with `ERROR: no NVIDIA GPU found` and changes
   nothing (`--no-gpu-check` continues anyway).
2. **uv.** When `uv` is not on the `PATH`, setup installs it with its official installer
   (`curl -LsSf https://astral.sh/uv/install.sh | sh` on Linux, `irm https://astral.sh/uv/install.ps1 | iex` in
   PowerShell on Windows) and finds it where the installer puts it (`~/.local/bin/uv`,
   `%USERPROFILE%\.local\bin\uv.exe`), even before a new terminal sees the new `PATH`.
3. **The environment.** `uv sync` creates `.venv/` with Python 3.12 (from `.python-version`) and the dependencies of
   `pyproject.toml` (locked in `uv.lock`), with PyTorch built for CUDA 12.8.
4. **The rest**, done by `python -m aigen.install` with the new environment's Python (`aigen/install.py`, standard
   library only, the same on both systems):
   - creates `models/checkpoints/`, `models/loras/`, `models/upscalers/`, `models/detectors/`, `characters/` and
     `output/`;
   - downloads the three models (below). It first checks the free disk space, downloads each file to a `.partial`
     file with its progress, checks its size and SHA256 and only then renames it. A file already in place with the
     right size is kept (its SHA256 is checked only with `--verify`); a file of another size, or one that fails
     `--verify`, is reported and left alone (delete it and run setup again). A download with a wrong SHA256 is an
     `ERROR:` and its partial file is removed; an interrupted one is resumed on the next run when the server allows
     it. When the configuration already points to another existing file for a model (`AIGEN_CHECKPOINT`, or a
     `config.local.ini` of yours), that file is used and nothing is downloaded;
   - writes `config.local.ini` with `checkpoint = models/checkpoints/ponyDiffusionV6XL.safetensors`, **only when the
     file does not exist**. An existing one is left alone; setup only warns when the checkpoint it points to is
     missing;
   - prints whether PyTorch sees the GPU;
   - creates the shortcut: on Linux an "AIGenerator" entry in the application menu (freedesktop, for GNOME, KDE, ...)
     that runs `bin/open_web.sh` in a terminal; on Windows `AIGenerator.lnk` on the Desktop and in the Start Menu, which
     runs `open_web.bat` in a console window ([web.md](web.md));
   - ends with a summary of what was done and "Open AIGenerator from the shortcut".

The exit code is 0 when everything was done, 1 when a step failed (uv, `uv sync`, a download, a hash, the shortcut;
the summary says which) and 2 for a wrong option or when there is no NVIDIA GPU (nothing was done).

| Option | What it does |
|---|---|
| `--no-models` | Downloads no model (for example, to put the checkpoint in place by hand) |
| `--no-shortcut` | Creates no shortcut |
| `--verify` | Checks the SHA256 of the models already in place too (a minute or more for the checkpoint) |
| `--no-gpu-check` | Continues without an NVIDIA GPU (generation on the CPU is far too slow to be useful) |
| `--icon FILE` | The shortcut's icon: an `.svg` or `.png` on Linux, an `.ico` on Windows (default: the one the shortcut already has, or the system's) |
| `--remove-shortcut` | Only removes the shortcut (skips the GPU check, uv and `uv sync`), and stops |

The same options on both systems: `./setup.sh --no-models`, `setup.bat --no-models`.

### The Civitai token

Civitai may ask for an account to download a model (the download then fails with a 401 or 403 answer, or with a
login page instead of the file). In that case, create an API key in your Civitai account settings and set it only
for the run:

```
AIGEN_CIVITAI_TOKEN=your_key ./setup.sh          (Linux)

set AIGEN_CIVITAI_TOKEN=your_key                 (Windows, in a Command Prompt)
setup.bat
```

The key is sent only to `civitai.com` (as `Authorization: Bearer`; not to the storage server Civitai redirects to)
and is never written anywhere.

### When a download fails

The message says where the file comes from and where to put it, and the rest of setup still runs. To do it by hand:
download the file from the model page, save it at the path in the table below and run setup again (it checks the
size and keeps it). A checkpoint saved elsewhere works too: set its path in `config.local.ini` (below).

## The models

| What | Where (default) | Size | From |
|---|---|---|---|
| The checkpoint: Pony Diffusion V6 XL | `models/checkpoints/ponyDiffusionV6XL.safetensors` | 6.9 GB | [Civitai](https://civitai.com/models/257749/pony-diffusion-v6-xl) (version "V6") |
| The upscaler for the hires fix: RealESRGAN_x4plus_anime_6B | `models/upscalers/RealESRGAN_x4plus_anime_6B.pth` | 18 MB | [Real-ESRGAN v0.2.2.4](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.2.4) |
| The face detector for the face fix: lbpcascade_animeface | `models/detectors/lbpcascade_animeface.xml` | 247 KB | [lbpcascade_animeface](https://github.com/nagadomi/lbpcascade_animeface) |
| LoRAs (optional, not downloaded) | `models/loras/` (subfolders allowed) | | `.safetensors` files trained for Pony / SDXL |

The exact URLs, sizes and SHA256 values are in `aigen/install.py` (`MODELS`). Before downloading the checkpoint,
setup prints that **its license (a modified Fair AI Public License 1.0-SD) is set by its author**: read it on the
model page before using the model, in particular for commercial use. The upscaler (BSD-3-Clause) and the face
detector (MIT) allow commercial use; see [licenses.md](licenses.md). Another SDXL checkpoint works too: set its path
as `checkpoint` in `config.local.ini`.

The first time a checkpoint is loaded, diffusers downloads the SDXL pipeline configuration files (a few kilobytes,
from Hugging Face) and caches them.

## Without setup

The manual steps, for another environment or when setup cannot run:

1. Install [uv](https://docs.astral.sh/uv/) and run `uv sync` in the repository folder (or use your own Python 3.11+
   environment with the dependencies of `pyproject.toml`, and set `AIGEN_PYTHON` to its interpreter: the launchers
   use it instead of `.venv/`).
2. Download the models of the table above to their paths.
3. Write `config.local.ini` with the checkpoint's path (below).
4. Optional: `python -m aigen.install --no-models` (from the repository folder, with the environment's Python) makes
   the folders, `config.local.ini` (when missing) and the shortcut; `--remove-shortcut` removes the shortcut.

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
| `AIGEN_SAVE_PROMPTS` | `[privacy] save_prompts` | `true`; `false` turns private mode on for every run: the prompts are not saved in the PNG or the report ([contract.md](contract.md), "Private mode"). Accepts `true`/`false`, `yes`/`no`, `1`/`0`, `on`/`off`, in any case; `--private`, `--save-prompts` and the web interface's box override it for one run |

Relative paths are relative to the repository root; `~` is the home folder. `models/`, `characters/` and `output/`
are ignored by git.
