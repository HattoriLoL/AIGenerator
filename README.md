# AIGenerator

Anime character image generation with Pony Diffusion XL (SDXL), from the command line, in batches or in a local web
interface, with character sheets, LoRAs, hires fix and face fix.

## What it does
**A request goes in; a PNG and a JSON report come out.** The request is a JSON file or a set of command-line options:
the scene tags, an optional character sheet, the size, the sampler, the seed, LoRAs and the optional passes.

- **Character sheets:** a small TOML file per character keeps the tags that do not change (hair, eyes, outfit, the
  character's LoRA), the checkpoint and the settings that give it its look, so each request only describes the scene. See [docs/sheets.md](docs/sheets.md).
- **Anime by default, Pony-aware prompts:** the `score_9, score_8_up, ...` quality tags, the `source_anime` style tag
  and `rating_safe` (with the other sources, 3D, realism and explicit ratings in the negative) are added for you;
  each one can be turned off. Tags are not repeated, and AUTOMATIC1111 weights (`(tag:1.2)`) and long prompts work.
- **LoRAs** from a folder, with a weight each, from the request, the sheet or the interface.
- **Hires fix** (off by default): upscale with an anime upscaler model and redraw the details in a second pass.
- **Face fix** (off by default): find the anime faces, redraw each one at 1024 px and paste it back.
- **Reproducible outputs:** every PNG carries its full request (and the AUTOMATIC1111 `parameters` text that other
  tools read), and a report with the seed and the time of each stage goes next to it. Nothing is ever overwritten.
- **Private mode:** prompts can be kept out of the files (`--private`, a box in the web interface or a config key):
  the PNG then carries no metadata and the report only the numbers.
- **Scriptable:** documented exit codes, `ERROR:` messages, versioned formats, and a batch mode that loads the model
  once for a whole folder of requests.

## Requirements and installation
An **NVIDIA GPU** (16 GB is comfortable; RTX 50 cards are supported through PyTorch for CUDA 12.8), Linux or Windows
10/11 (Windows is [not tested yet](docs/windows.md)) and about 20 GB of free disk space. Then one command:

| System | Run |
|---|---|
| Linux | `./setup.sh` |
| Windows | double-click `setup.bat` |

Setup checks for the GPU, installs [uv](https://docs.astral.sh/uv/) if it is missing, creates the environment in
`.venv/` (Python 3.12 and PyTorch), downloads Pony Diffusion V6 XL, the upscaler (hires fix) and the face detector
(face fix) with their SHA256 checked, writes `config.local.ini` and adds an "AIGenerator" shortcut (application menu
on Linux; Desktop and Start Menu on Windows). It is safe to run again: what is done is skipped and your files are
never overwritten. Then **open AIGenerator from the shortcut**: the web interface opens in the browser.

The steps, the options (`--no-models`, `--no-shortcut`, `--verify`, `--no-gpu-check`, ...), the manual way and all
the settings: [docs/installation.md](docs/installation.md).

## Running
```
bin/aigen.sh output.png --prompt "1girl, solo, smile, school uniform, classroom"
bin/aigen.sh output.png --sheet my_character --prompt "sitting, cafe, night" --hires --face-fix
bin/aigen.sh output.png --request request.json
bin/aigen_batch.sh requests_folder output_folder
bin/aigen_web.sh                                   (http://127.0.0.1:7860)
```
On Windows the same launchers are `aigen.bat`, `aigen_batch.bat` and `aigen_web.bat`
([docs/windows.md](docs/windows.md)). The shortcut runs the web interface in a terminal window; closing it frees the
GPU ([docs/web.md](docs/web.md)).
Next to `output.png` you get `output.aigen.json` (the report). The exit code is 0 on success, 1 when the image could
not be made and 2 when the request is wrong and nothing was done (the message starts with `ERROR:`; see
[docs/contract.md](docs/contract.md)).

All the options are explained in [docs/options.md](docs/options.md).

## Documentation
| File | Topic |
|---|---|
| [docs/installation.md](docs/installation.md) | Setup, the models and the configuration |
| [docs/windows.md](docs/windows.md) | Windows: setup, the launchers, the shortcut and a first-run checklist |
| [docs/options.md](docs/options.md) | All options, batch mode and examples |
| [docs/contract.md](docs/contract.md) | The contract: the request, the outputs, the versions and the exit codes |
| [docs/sheets.md](docs/sheets.md) | Character sheets |
| [docs/web.md](docs/web.md) | The web interface |
| [docs/how-it-works.md](docs/how-it-works.md) | The stages: prompt, model, LoRAs, generation, hires fix, face fix, output |
| [docs/limitations.md](docs/limitations.md) | What is not supported and what needs care |
| [docs/licenses.md](docs/licenses.md) | Third-party licenses and the models' licenses |
| [examples/README.md](examples/README.md) | The example request and character sheet |

## Folders
| Folder | Contents |
|---|---|
| `aigen/` | The code |
| `bin/` | The Linux launchers, the Python lookups and the secret scanner (`setup.sh`, `setup.bat` and the Windows launchers are in the root) |
| `tests/` | Automated tests (no GPU, no image generation) |
| `examples/` | An example request and character sheet |
| `docs/` | The documentation, one file per topic |
| `models/`, `characters/`, `output/` | Models, your character sheets and the outputs (created by setup, ignored by git) |

## Tests
`tests/run.sh` runs the whole suite in a few seconds with any Python 3.11+, without PyTorch or a GPU: the contract,
the prompt assembly, the sheets, the metadata, the stage sequences and the code rules. No test generates an image:
checking images is done by a person.

## Status
Early: version 0.1, used on Linux with an NVIDIA RTX 50-series GPU (16 GB); not tested on Windows yet. The formats are versioned
([docs/contract.md](docs/contract.md)) but may still change before 1.0.

## Content
Pony Diffusion XL can produce adult content. AIGenerator blocks explicit ratings by default (`rating_safe` in the
prompt, the explicit ratings in the negative; see [docs/contract.md](docs/contract.md)), but no prompt-based filter
is perfect. You are responsible for what you generate and for following the model's license.

## Limitations
SDXL checkpoints only, NVIDIA GPUs only, one generation at a time; the full list is in
[docs/limitations.md](docs/limitations.md).

## Support
AIGenerator is provided as is, without guaranteed support. Issues and pull requests are welcome, but they may not get
a response.

## License
AIGenerator is licensed under the [GNU General Public License v3.0](LICENSE). The repository contains no model
weights; the models you download have their own licenses (see [docs/licenses.md](docs/licenses.md)).
