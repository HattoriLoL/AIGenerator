# Character sheets

[Back to the README](../README.md)

A character sheet keeps what does not change from one image of a character to the next (hair, eyes, outfit, the
character's LoRA, the checkpoint and the generation settings that give the character its look) so the scene prompt
only says what changes (pose, place, expression). It is a TOML file, one per character, in the sheets folder
(`characters/` by default, ignored by git). The web interface's "Sheets" tab creates and edits them; any text editor
works too.

```toml
sheet_version = 1
name = "Example"
tags = "1girl, solo, long silver hair, straight hair, red eyes, black hoodie, white pleated skirt"
negative = "monochrome, 3d"
checkpoint = "ponyDiffusionV6XL"
notes = "Free text, not used in the prompt."

[settings]
width = 832
height = 1216
steps = 30
cfg = 6.5
sampler = "dpmpp_2m_karras"

[settings.hires]
scale = 1.5
strength = 0.35

[[loras]]
name = "my_character_v1"
weight = 0.9
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `sheet_version` | 1 | 1 | Format version |
| `name` | text | required | The character's name (the web interface names the file after it: lower case, no accents) |
| `tags` | text | `""` | Tags that describe the character, comma-separated, with AUTOMATIC1111 weights |
| `negative` | text | `""` | Negative tags for this character |
| `checkpoint` | text | `""` | The checkpoint the character is made with: its file name, with or without `.safetensors`/`.ckpt`, without the folder. Empty: any checkpoint |
| `notes` | text | `""` | Notes; not used in the prompt |
| `settings` | table | none | The generation settings of the character (below) |
| `loras` | list of tables | none | `name` (a file in the LoRA folder) and `weight` (-4 to 4, default 1) |

Unknown fields are refused. In a request, `"sheet": "example"` looks up `characters/example.toml`; a value ending in
`.toml` or containing `/` is a path. The prompt order is: quality tags, style tags, rating tags, the sheet's tags, the
scene prompt, without repeated tags (so the sheet does not need `source_anime`). For a LoRA in both the sheet and the
request, the request's weight wins.

## Settings

The `[settings]` table keeps the settings that change the look of every image of the character, so they stay the same
from one image to the next. Each field is optional and means the same as the request field of the same name
([contract.md](contract.md)):

| Field | Values |
|---|---|
| `quality` | `true` or `false` |
| `style` | `"anime"` or `"none"` (the request's `null`: no source tags) |
| `block_explicit` | `true` or `false` |
| `width`, `height` | A multiple of 8 from 256 to 2048 |
| `steps` | 1 to 150 |
| `cfg` | 1 to 30 |
| `sampler` | One of the request's samplers |
| `hires`, `face_fix` | `false` (off), `true` (on with the defaults) or a table, `[settings.hires]` or `[settings.face_fix]`, with the request's fields (`scale`, `strength`, ...; the missing ones take the defaults) |

The seed and the count are not settings: they change from one image to the next.

**The request wins.** A setting is used only where the request (or a command-line option) does not give that field:
with `steps = 30` in the sheet, `--sheet example` generates with 30 steps and `--sheet example --steps 40` with 40.
For `hires` and `face_fix`, a request that turns the pass on (`--hires`, `"hires": true`) takes the sheet's fields, and
a request that gives some of them (`--hires-steps 10`) takes the others from the sheet; `"hires": null` or `false` in
the request turns it off. The request kept in the PNG and in the report has the values that were used, so it makes the
same image again even after the sheet changes.

In the web interface, choosing a sheet in the Generate tab fills in the fields its settings set (the others are left
as they are); the Sheets tab's button "Use the Generate tab's settings and the configured checkpoint" writes the
Generate tab's settings and the checkpoint's name into the sheet being edited, to be saved with it.

## Checkpoint

A sheet with a `checkpoint` only generates with that checkpoint: when the configured one (`[models] checkpoint` in
`config.local.ini`, or `AIGEN_CHECKPOINT`) is another file, the request is refused with exit code 2 before the model
is loaded, so a character is not made by mistake with another model. The file name is compared without the folder and
the extension, in any case.

An example sheet is in [examples/characters/example.toml](../examples/characters/example.toml).
