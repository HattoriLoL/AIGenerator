# Options

[Back to the README](../README.md)

```
bin/aigen.sh output.png [options]
bin/aigen_lote.sh requests_folder output_folder
bin/aigen_web.sh [--porta N]
```

The option names are in Portuguese; each one sets the request field of the same meaning ([contrato.md](contrato.md))
and overrides the field of `--pedido`.

## Generation

| Option | Field | Meaning |
|---|---|---|
| `output.png` | | The PNG to write (never overwritten); the report goes next to it as `output.aigen.json` |
| `--pedido FILE` | | A request in JSON; the options below override its fields |
| `--prompt TEXT` | `prompt` | The scene tags |
| `--negativo TEXT` | `negativo` | The negative tags |
| `--ficha NAME` | `ficha` | A character sheet: a name in the sheets folder or the path of a `.toml` |
| `--sem-qualidade` | `qualidade: false` | Do not add the Pony `score_*` tags |
| `--estilo anime\|nenhum` | `estilo` | The Pony source tags (default: anime); `nenhum` adds none |
| `--permitir-explicito` | `bloquear_explicito: false` | Do not add the tags that block explicit ratings (`rating_safe`, ...) |
| `--largura N`, `--altura N` | `largura`, `altura` | Size, a multiple of 8 from 256 to 2048 (Pony works best near one megapixel: 1024×1024, 832×1216, 1216×832, ...) |
| `--passos N` | `passos` | Steps |
| `--cfg X` | `cfg` | Guidance scale |
| `--amostrador NAME` | `amostrador` | The sampler |
| `--seed N` | `seed` | The seed; -1 draws one |
| `--quantidade N` | `quantidade` | How many images; they come out as `output_001.png`, `output_002.png`, ... |
| `--lora NAME[:WEIGHT]` | `loras` | A LoRA from the LoRA folder; repeat for more. Added to the request's and the sheet's |
| `--versao` | | Print the version |

## Hires fix (off by default)

| Option | Field | Meaning |
|---|---|---|
| `--hires` | `hires` | Turn it on (with the defaults, or the request's values) |
| `--hires-escala X` | `hires.escala` | Size factor |
| `--hires-forca X` | `hires.forca` | Denoising strength |
| `--hires-passos N` | `hires.passos` | Steps of the second pass |
| `--hires-upscaler modelo\|lanczos` | `hires.upscaler` | The upscaler |

Any `--hires-*` option also turns it on.

## Face fix (off by default)

| Option | Field | Meaning |
|---|---|---|
| `--rosto` | `rosto` | Turn it on |
| `--rosto-forca X` | `rosto.forca` | Inpaint strength |
| `--rosto-passos N` | `rosto.passos` | Steps per face |
| `--rosto-margem X` | `rosto.margem` | Context around each face |
| `--rosto-prompt TEXT` | `rosto.prompt` | Extra tags for the face |
| `--rosto-max N` | `rosto.max_rostos` | Faces to fix at most |

Any `--rosto-*` option also turns it on.

## Examples

```
bin/aigen.sh saida/a.png --prompt "1girl, solo, smile, school uniform, classroom"
bin/aigen.sh saida/b.png --ficha exemplo --prompt "sitting, cafe, night" --seed 42 --hires --rosto
bin/aigen.sh saida/c.png --pedido examples/pedido.json --seed 7 --quantidade 4
```

## Batch mode

`bin/aigen_lote.sh requests_folder output_folder` runs every `*.json` of the folder (sorted by name) with one model
load. Each `x.json` becomes `output_folder/x.png` (or `x_001.png`, ...). A wrong or failed request does not stop the
others; the summary goes to `output_folder/lote.aigen.json` ([contrato.md](contrato.md)). Relative sheet paths in the
requests are relative to the current folder, not to the requests folder.

## Web interface

`bin/aigen_web.sh` serves the interface at `http://127.0.0.1:7860` (only on this machine); see [web.md](web.md).
