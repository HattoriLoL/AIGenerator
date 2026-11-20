# Options

[Back to the README](../README.md)

```
bin/aigen.sh output.png [options]
bin/aigen_batch.sh requests_folder output_folder
bin/aigen_web.sh [--port N] [--open]
```

Each option sets the request field of the same meaning ([contract.md](contract.md)) and overrides the field of
`--request`.

## Generation

| Option | Field | Meaning |
|---|---|---|
| `output.png` | | The PNG to write (never overwritten); the report goes next to it as `output.aigen.json` |
| `--request FILE` | | A request in JSON; the options below override its fields |
| `--prompt TEXT` | `prompt` | The scene tags |
| `--negative TEXT` | `negative` | The negative tags |
| `--sheet NAME` | `sheet` | A character sheet: a name in the sheets folder or the path of a `.toml`. Its settings fill the fields that neither the options nor `--request` give ([sheets.md](sheets.md)) |
| `--no-quality` | `quality: false` | Do not add the Pony `score_*` tags |
| `--style anime\|none` | `style` | The Pony source tags (default: anime); `none` adds none |
| `--allow-explicit` | `block_explicit: false` | Do not add the tags that block explicit ratings (`rating_safe`, ...) |
| `--width N`, `--height N` | `width`, `height` | Size, a multiple of 8 from 256 to 2048 (Pony works best near one megapixel: 1024×1024, 832×1216, 1216×832, ...) |
| `--steps N` | `steps` | Steps |
| `--cfg X` | `cfg` | Guidance scale |
| `--sampler NAME` | `sampler` | The sampler |
| `--seed N` | `seed` | The seed; -1 draws one |
| `--count N` | `count` | How many images; they come out as `output_001.png`, `output_002.png`, ... |
| `--lora NAME[:WEIGHT]` | `loras` | A LoRA from the LoRA folder; repeat for more. Added to the request's and the sheet's |
| `--version` | | Print the version |

## Hires fix (off by default)

| Option | Field | Meaning |
|---|---|---|
| `--hires` | `hires` | Turn it on (with the defaults, or the request's values) |
| `--hires-scale X` | `hires.scale` | Size factor |
| `--hires-strength X` | `hires.strength` | Denoising strength |
| `--hires-steps N` | `hires.steps` | Steps of the second pass |
| `--hires-upscaler model\|lanczos` | `hires.upscaler` | The upscaler |

Any `--hires-*` option also turns it on.

## Face fix (off by default)

| Option | Field | Meaning |
|---|---|---|
| `--face-fix` | `face_fix` | Turn it on |
| `--face-fix-strength X` | `face_fix.strength` | Inpaint strength |
| `--face-fix-steps N` | `face_fix.steps` | Steps per face |
| `--face-fix-margin X` | `face_fix.margin` | Context around each face |
| `--face-fix-prompt TEXT` | `face_fix.prompt` | Extra tags for the face |
| `--face-fix-max N` | `face_fix.max_faces` | Faces to fix at most |

Any `--face-fix-*` option also turns it on.

## Privacy

| Option | Meaning |
|---|---|
| `--private` | Do not save the prompts: the PNG gets no text chunk and the `.aigen.json` report leaves out the prompts, the sheet and the LoRAs ([contract.md](contract.md), "Private mode") |
| `--save-prompts` | Save the prompts in the PNG and the report (the default) |

They override `[privacy] save_prompts` of the config ([installation.md](installation.md)) for that run; giving both
is an option error (code 2). They are not request fields: a request never carries them. The batch mode takes them
too, for every request of the folder. Note that your shell may keep the command line, `--prompt` included, in its
history; a `--request` file is yours to keep or delete.

## Examples

```
bin/aigen.sh output/a.png --prompt "1girl, solo, smile, school uniform, classroom"
bin/aigen.sh output/b.png --sheet example --prompt "sitting, cafe, night" --seed 42 --hires --face-fix
bin/aigen.sh output/c.png --request examples/request.json --seed 7 --count 4
```

## Batch mode

`bin/aigen_batch.sh requests_folder output_folder [--private | --save-prompts]` runs every `*.json` of the folder (sorted by name) with one model
load. Each `x.json` becomes `output_folder/x.png` (or `x_001.png`, ...). A wrong or failed request does not stop the
others; the summary goes to `output_folder/batch.aigen.json` ([contract.md](contract.md)). Relative sheet paths in the
requests are relative to the current folder, not to the requests folder.

## Web interface

`bin/aigen_web.sh` serves the interface at `http://127.0.0.1:7860` (only on this machine); see [web.md](web.md).
