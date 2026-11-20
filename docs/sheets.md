# Character sheets

[Back to the README](../README.md)

A character sheet keeps what does not change from one image of a character to the next (hair, eyes, outfit, the
character's LoRA) so the scene prompt only says what changes (pose, place, expression). It is a TOML file, one per
character, in the sheets folder (`characters/` by default, ignored by git). The web interface's "Sheets" tab creates
and edits them; any text editor works too.

```toml
sheet_version = 1
name = "Example"
tags = "1girl, solo, long silver hair, straight hair, red eyes, black hoodie, white pleated skirt"
negative = "monochrome, 3d"
notes = "Free text, not used in the prompt."

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
| `notes` | text | `""` | Notes; not used in the prompt |
| `loras` | list of tables | none | `name` (a file in the LoRA folder) and `weight` (-4 to 4, default 1) |

Unknown fields are refused. In a request, `"sheet": "example"` looks up `characters/example.toml`; a value ending in
`.toml` or containing `/` is a path. The prompt order is: quality tags, style tags, rating tags, the sheet's tags, the
scene prompt, without repeated tags (so the sheet does not need `source_anime`). For a LoRA in both the sheet and the
request, the request's weight wins.

An example sheet is in [examples/characters/example.toml](../examples/characters/example.toml).
