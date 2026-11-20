# Input and output contract

[Back to the README](../README.md)

What other programs can rely on: the request, the character sheet, the outputs, the format versions and the exit
codes. It is checked by `aigen/contract.py` and `aigen/sheets.py`.

## Versions

| Format | Field | Current |
|---|---|---|
| The request (JSON) | `request_version` (absent means 1) | 1 |
| The character sheet (TOML) | `sheet_version` (absent means 1) | 1 |
| The report `.aigen.json`, the batch summary `batch.aigen.json` and the PNG `aigen` chunk | `format_version` | 1 |

A version goes up only when a field changes meaning or is removed. A new optional field does not change it.

## Exit codes

The same in `bin/aigen.sh` and `bin/aigen_batch.sh`:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | An image could not be made: the model did not load, the GPU ran out of memory, a stage failed. In batch mode: some request failed |
| 2 | The request is wrong and nothing was loaded or written: an invalid option or field, a missing sheet, LoRA, checkpoint, upscaler or detector, a sheet made with another checkpoint, a missing library, an output that already exists |

Every error message starts with `ERROR:`.

## The request, version 1

A JSON object. Unknown fields are refused (they are almost always typos). The command-line options override the
fields of `--request` ([options.md](options.md)).

| Field | Type | Default | Meaning |
|---|---|---|---|
| `request_version` | 1 | 1 | Format version |
| `prompt` | text | `""` | The scene tags, comma-separated, with AUTOMATIC1111 weights (`(tag:1.2)`) |
| `negative` | text | `""` | The negative tags |
| `sheet` | text or null | null | A character sheet: a name (looked up as `<name>.toml` in the sheets folder) or a path (ending in `.toml` or containing `/`, relative to the current folder). Its `[settings]` fill the fields the request does not give ([sheets.md](sheets.md)) |
| `quality` | bool | true | Put the Pony quality tags in front of the prompt and the negative ([how-it-works.md](how-it-works.md)) |
| `style` | `"anime"` or null | `"anime"` | Pony source tags: `"anime"` adds `source_anime` to the prompt and `source_cartoon, source_furry, source_pony, 3d, realistic, photorealistic` to the negative; null adds none |
| `block_explicit` | bool | true | Block explicit content ratings: adds `rating_safe` to the prompt and `rating_questionable, rating_explicit` to the negative; false adds no rating tags (write your own) |
| `width`, `height` | integer | 1024 | Size of the first pass: a multiple of 8 from 256 to 2048 |
| `steps` | integer | 25 | Steps, 1 to 150 |
| `cfg` | number | 7 | Guidance scale, 1 to 30 |
| `sampler` | text | `"euler_a"` | One of `euler_a`, `euler`, `dpmpp_2m`, `dpmpp_2m_karras`, `dpmpp_2m_sde_karras`, `ddim` |
| `seed` | integer | -1 | 0 to 2³²−1; -1 draws one (written in the report and the PNG) |
| `count` | integer | 1 | Number of images, 1 to 64, with consecutive seeds |
| `loras` | list | `[]` | `{"name": "file in the LoRA folder, with or without .safetensors", "weight": -4 to 4, default 1}` |
| `hires` | object, true or null | null | Hires fix: absent, null or false is off; true is on with the defaults; an object is on |
| `face_fix` | object, true or null | null | Face fix, same rule as `hires` |

A request needs a non-empty `prompt` or a `sheet`.

`hires` fields:

| Field | Default | Meaning |
|---|---|---|
| `scale` | 1.5 | Size factor, greater than 1 and up to 4; the larger side may not pass 4096 px |
| `strength` | 0.4 | Denoising strength of the second pass, greater than 0 and up to 1 |
| `steps` | 15 | Steps actually run in the second pass, 1 to 150 |
| `upscaler` | `"model"` | `"model"` (the upscaler model of the config) or `"lanczos"` (no model) |

`face_fix` fields:

| Field | Default | Meaning |
|---|---|---|
| `strength` | 0.4 | Inpaint strength, greater than 0 and up to 1 |
| `steps` | 20 | Steps actually run per face, 1 to 150 |
| `margin` | 0.3 | Context around the face, as a fraction of the face size on each side, 0 to 2 |
| `prompt` | `""` | Extra tags for the face only |
| `max_faces` | 4 | Faces to fix at most, 1 to 16, largest first |

## The character sheet, version 1

Described in [sheets.md](sheets.md).

## The outputs

For an output `x.png` (or `x_001.png`, `x_002.png`, ... with `count` > 1):

- **`x.png`**, with two text chunks:
  - `parameters`: the AUTOMATIC1111 text (prompt with `<lora:name:weight>`, `Negative prompt:`, and a line with
    `Steps`, `Sampler`, `CFG scale`, `Seed`, `Size`, `Model` and, when on, the hires fix and face fix values), which
    other tools and sites read;
  - `aigen`: JSON with `format_version`, `request` (the full request, with the seed used and `count` 1),
    `positive`, `negative` (the final prompts) and `loras`. The web interface's "Read PNG" tab rebuilds the request
    from it.
- **`x.aigen.json`**, the report: `format_version`, `aigen` (the version), `png`, `request`, `model` (the checkpoint
  file name), `seconds`, `timings` (seconds per stage), `memory` (per stage: `vram_peak_mb`, the most GPU memory
  allocated during the stage, `vram_reserved_mb`, what PyTorch keeps reserved at its end, and `ram_mb`, the process
  RAM at its end; each null where it could not be measured, see [how-it-works.md](how-it-works.md), "Memory"), `sheet` (the sheet's name or null), `prompt` (`positive` and
  `negative`), `loras`, `generation`, when on, `hires` and `face_fix` (`found`: the faces found, `boxes`: their
  boxes, and `strength`), and `private` (false; true in private mode, below).

### Private mode (the prompts not saved)

With `--private` ([options.md](options.md)), the web interface's "Don't save the prompt (private)" box
([web.md](web.md)) or `[privacy] save_prompts = false` in the config ([installation.md](installation.md)), nothing
written tells what the image is:

- **`x.png`** has **no text chunk at all**: neither `parameters` nor `aigen`. The request cannot be rebuilt from it
  (the "Read PNG" tab says it has no AIGenerator data).
- **`x.aigen.json`** is still written, with `"private": true`, but its `request` has no `prompt`, `negative`, `sheet`
  or `loras`, its `face_fix` (when on) has no `prompt`, and the report has no `sheet`, `prompt` or `loras` entry. What
  stays: `format_version`, `aigen`, `png`, `model`, `seconds`, `timings`, `generation`, `hires`, `face_fix` (the
  faces found, their boxes and the strength) and, in `request`, `request_version`, `seed`, `width`, `height`,
  `steps`, `cfg`, `sampler`, `count`, `quality`, `style`, `block_explicit`, `hires` and the `face_fix` numbers. This
  `request` is not a full request: given back to the tool, it is refused (it has nothing to generate).
- On a failed web generation, `aigen-web.log` gets the time and the error only, without the request.
- The batch summary holds no prompt in either mode.

No output is ever overwritten: an existing PNG or report is refused before anything is loaded (code 2).

### The batch summary (`batch.aigen.json`)

`format_version`, `aigen`, `failures` (how many requests failed) and `requests`: one item per request with `request`
(the file name), `ok`, `png` (the files written) or `error` (the `ERROR:` message), and `seconds`.

## History

- Version 1 of every format: the first public version.
- Version 1, renamed: before anyone depended on the formats, every field, value and message was renamed to English
  (for example `versao_pedido` became `request_version`, `rosto` became `face_fix` and the upscaler `"modelo"` became
  `"model"`). The version number stayed at 1; PNGs and files written with the Portuguese names are not read.
- Version 1, new field: the report's `private` (always present; true when the prompts were not saved). In private
  mode the report leaves out `prompt`, `sheet` and `loras`, and its `request` leaves out `prompt`, `negative`,
  `sheet`, `loras` and `face_fix.prompt`; normal mode, the default, writes every field as before, so the version
  stayed at 1.
