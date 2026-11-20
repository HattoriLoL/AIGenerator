# Input and output contract

[Back to the README](../README.md)

What other programs can rely on: the request (`pedido`), the character sheet (`ficha`), the outputs, the format
versions and the exit codes. It is checked by `aigen/contrato.py` and `aigen/fichas.py`.

## Versions

| Format | Field | Current |
|---|---|---|
| The request (JSON) | `versao_pedido` (absent means 1) | 1 |
| The character sheet (TOML) | `versao_ficha` (absent means 1) | 1 |
| The report `.aigen.json`, the batch summary `lote.aigen.json` and the PNG `aigen` chunk | `versao_formato` | 1 |

A version goes up only when a field changes meaning or is removed. A new optional field does not change it.

## Exit codes

The same in `bin/aigen.sh` and `bin/aigen_lote.sh`:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | An image could not be made: the model did not load, the GPU ran out of memory, a stage failed. In batch mode: some request failed |
| 2 | The request is wrong and nothing was loaded or written: an invalid option or field, a missing sheet, LoRA, checkpoint, upscaler or detector, a missing library, an output that already exists |

Every error message starts with `ERRO:`.

## The request, version 1

A JSON object. Unknown fields are refused (they are almost always typos). The command-line options override the
fields of `--pedido` ([opcoes.md](opcoes.md)).

| Field | Type | Default | Meaning |
|---|---|---|---|
| `versao_pedido` | 1 | 1 | Format version |
| `prompt` | text | `""` | The scene tags, comma-separated, with AUTOMATIC1111 weights (`(tag:1.2)`) |
| `negativo` | text | `""` | The negative tags |
| `ficha` | text or null | null | A character sheet: a name (looked up as `<name>.toml` in the sheets folder) or a path (ending in `.toml` or containing `/`, relative to the current folder) |
| `qualidade` | bool | true | Put the Pony quality tags in front of the prompt and the negative ([como-funciona.md](como-funciona.md)) |
| `estilo` | `"anime"` or null | `"anime"` | Pony source tags: `"anime"` adds `source_anime` to the prompt and `source_cartoon, source_furry, source_pony, 3d, realistic, photorealistic` to the negative; null adds none |
| `bloquear_explicito` | bool | true | Block explicit content ratings: adds `rating_safe` to the prompt and `rating_questionable, rating_explicit` to the negative; false adds no rating tags (write your own) |
| `largura`, `altura` | integer | 1024 | Size of the first pass: a multiple of 8 from 256 to 2048 |
| `passos` | integer | 25 | Steps, 1 to 150 |
| `cfg` | number | 7 | Guidance scale, 1 to 30 |
| `amostrador` | text | `"euler_a"` | One of `euler_a`, `euler`, `dpmpp_2m`, `dpmpp_2m_karras`, `dpmpp_2m_sde_karras`, `ddim` |
| `seed` | integer | -1 | 0 to 2³²−1; -1 draws one (written in the report and the PNG) |
| `quantidade` | integer | 1 | Number of images, 1 to 64, with consecutive seeds |
| `loras` | list | `[]` | `{"nome": "file in the LoRA folder, with or without .safetensors", "peso": -4 to 4, default 1}` |
| `hires` | object, true or null | null | Hires fix: absent, null or false is off; true is on with the defaults; an object is on |
| `rosto` | object, true or null | null | Face fix, same rule as `hires` |

A request needs a non-empty `prompt` or a `ficha`.

`hires` fields:

| Field | Default | Meaning |
|---|---|---|
| `escala` | 1.5 | Size factor, greater than 1 and up to 4; the larger side may not pass 4096 px |
| `forca` | 0.4 | Denoising strength of the second pass, greater than 0 and up to 1 |
| `passos` | 15 | Steps actually run in the second pass, 1 to 150 |
| `upscaler` | `"modelo"` | `"modelo"` (the upscaler model of the config) or `"lanczos"` (no model) |

`rosto` fields:

| Field | Default | Meaning |
|---|---|---|
| `forca` | 0.4 | Inpaint strength, greater than 0 and up to 1 |
| `passos` | 20 | Steps actually run per face, 1 to 150 |
| `margem` | 0.3 | Context around the face, as a fraction of the face size on each side, 0 to 2 |
| `prompt` | `""` | Extra tags for the face only |
| `max_rostos` | 4 | Faces to fix at most, 1 to 16, largest first |

## The character sheet, version 1

Described in [fichas.md](fichas.md).

## The outputs

For an output `x.png` (or `x_001.png`, `x_002.png`, ... with `quantidade` > 1):

- **`x.png`**, with two text chunks:
  - `parameters`: the AUTOMATIC1111 text (prompt with `<lora:name:weight>`, `Negative prompt:`, and a line with
    `Steps`, `Sampler`, `CFG scale`, `Seed`, `Size`, `Model` and, when on, the hires fix and face fix values), which
    other tools and sites read;
  - `aigen`: JSON with `versao_formato`, `pedido` (the full request, with the seed used and `quantidade` 1),
    `positivo`, `negativo` (the final prompts) and `loras`. The web interface's "Ler PNG" tab rebuilds the request
    from it.
- **`x.aigen.json`**, the report: `versao_formato`, `aigen` (the version), `png`, `pedido`, `modelo` (the checkpoint
  file name), `segundos`, `tempos` (seconds per stage), `ficha` (the sheet's name or null), `prompt`, `loras`,
  `geracao` and, when on, `hires` and `rosto` (the faces found and their boxes).

No output is ever overwritten: an existing PNG or report is refused before anything is loaded (code 2).

### The batch summary (`lote.aigen.json`)

`versao_formato`, `aigen`, `falhas` (how many requests failed) and `pedidos`: one item per request with `pedido` (the
file name), `ok`, `png` (the files written) or `erro` (the `ERRO:` message), and `segundos`.

## History

- Version 1 of every format: the first public version.
