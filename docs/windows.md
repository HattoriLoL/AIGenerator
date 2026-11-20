# Windows

[Back to the README](../README.md)

**Not tested on Windows yet.** The Windows files were written and checked on Linux (their structure, CRLF line
endings and ASCII text, by `tests/test_contract.py`, class `Launchers`), but nobody has run them on Windows. If you
do, the [first-run checklist](#first-run-checklist) below says what to look at; please report what you find.

Requirements: Windows 10 or 11 (64-bit), an **NVIDIA GPU** with a recent driver (AMD and Intel GPUs are not
supported) and about 20 GB of free disk space ([installation.md](installation.md)).

## Setup

Get the repository (`git clone`, or the ZIP from GitHub, extracted to a folder of your choice) and **double-click
`setup.bat`**. It checks for the NVIDIA GPU, installs [uv](https://docs.astral.sh/uv/) when it is missing (with the
official PowerShell installer), creates the environment in `.venv\` (`uv sync`: Python 3.12 and PyTorch for CUDA
12.8), downloads the models, writes `config.local.ini` and creates the shortcuts. When it was started with a
double-click, it waits for a key at the end so the window can be read. It is safe to run again; the steps and the
options are in [installation.md](installation.md):

```
setup.bat [--no-models] [--no-shortcut] [--verify] [--no-gpu-check] [--icon FILE.ico] [--remove-shortcut]
```

Everything is plain `.bat` files, readable in any text editor, and a Python environment: there is no `.exe` to
download, sign or trust. A ZIP downloaded with a browser marks its files as coming from the internet, and Windows
may ask for a confirmation before running `setup.bat`; to avoid it, right click the ZIP > Properties > Unblock before
extracting it, or use `git clone`.

## The launchers

| Linux | Windows | What it does |
|---|---|---|
| `./setup.sh` | `setup.bat` | Installs everything ([installation.md](installation.md)) |
| `bin/aigen.sh` | `aigen.bat` | Generates images ([options.md](options.md)) |
| `bin/aigen_batch.sh` | `aigen_batch.bat` | Batch mode |
| `bin/aigen_web.sh` | `aigen_web.bat` | The web interface ([web.md](web.md)) |
| `bin/open_web.sh` | `open_web.bat` | What the shortcut runs |
| `tests/run.sh` | `tests\run.bat` | The automated tests |

The Windows launchers are in the repository root. They all find Python through `bin\_python.bat`, in the same order
as `bin/_python.sh`: the `AIGEN_PYTHON` variable, then `.venv\Scripts\python.exe`. Without either, they print
`ERROR: the AIGenerator environment is not installed: run setup.bat` and exit with code 2. `tests\run.bat` uses
`AIGEN_PYTHON_TESTS` when it is set. The options, the outputs and the exit codes are the same as on Linux, and the
messages name the Windows launchers (`aigen.bat --help`).

## The shortcut

Setup puts `AIGenerator.lnk` on the Desktop and in the Start Menu (through PowerShell and `WScript.Shell`). It runs
`open_web.bat` in a console window: if the interface already answers on its port (`[web] port`, 7860 by default),
it only opens the browser; otherwise it starts the interface there and opens the browser when it is ready. **Closing
the console window stops the interface and frees the GPU memory.** The shortcut runs `cmd.exe`, so it can be pinned
to the taskbar. `setup.bat --remove-shortcut` removes both.

## First-run checklist

For the first person who runs AIGenerator on Windows. In a Command Prompt in the repository folder, unless it says
double-click:

| # | Do | Expected |
|---|---|---|
| 1 | `tests\run.bat` (needs a Python 3.11+: run it after setup, or with `set AIGEN_PYTHON_TESTS=<a python.exe>`) | ends with `== all passed`; `echo %ERRORLEVEL%` gives 0 |
| 2 | Double-click `setup.bat` | the GPU line, uv found or installed, `uv sync` finishing, the license note, the three downloads with progress, `written: config.local.ini`, a `PyTorch ..., CUDA: <your GPU>` line, two `shortcut:` lines, then `Done.` and the window waits for a key |
| 3 | Double-click `setup.bat` again | nothing is downloaded again (`already there: ...`), `kept: config.local.ini`, `Done.` |
| 4 | `setup.bat --bogus` | `ERROR: unknown option: --bogus`, exit code 2 |
| 5 | With a folder name that has a space (move the clone to, for example, `C:\AI Generator`) and run setup again | everything works; the shortcuts point to the new place |
| 6 | Open the Start Menu, type "AIGenerator", and open it | a console window opens, then the browser at `http://127.0.0.1:7860` |
| 7 | Generate an image with the default fields | a PNG and its `.aigen.json` in `output\<date>\` |
| 8 | Generate again with "Face fix" (and "Hires fix") on | the image is made; the report lists the stages and the faces found |
| 9 | Open the shortcut again while it runs | only a browser tab opens (no second console) |
| 10 | Close the console window, then look at the GPU memory (`nvidia-smi`, or Task Manager > Performance > GPU) | the memory the interface used (about 7 GB) is free again |
| 11 | `aigen.bat %TEMP%\a.png --prompt "1girl, smile"` | exit code 0; `%TEMP%\a.png` and `%TEMP%\a.aigen.json` |
| 12 | `set AIGEN_PYTHON=C:\does\not\exist.exe` and `aigen.bat --help` | the system's "is not recognized" message; then `set AIGEN_PYTHON=` |
| 13 | Rename `.venv` for a moment and run `aigen.bat --help` | `ERROR: the AIGenerator environment is not installed: run setup.bat ...`, exit code 2; rename it back |
| 14 | `setup.bat --remove-shortcut` | both shortcuts are gone |

Worth writing down when something fails: the Windows version, the GPU and driver version (`nvidia-smi`), the folder
of the clone, and the console output.
