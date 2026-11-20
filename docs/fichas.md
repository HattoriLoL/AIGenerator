# Character sheets

[Back to the README](../README.md)

A character sheet keeps what does not change from one image of a character to the next (hair, eyes, outfit, the
character's LoRA) so the scene prompt only says what changes (pose, place, expression). It is a TOML file, one per
character, in the sheets folder (`personagens/` by default, ignored by git). The web interface's "Fichas" tab creates
and edits them; any text editor works too.

```toml
versao_ficha = 1
nome = "Exemplo"
tags = "1girl, solo, long silver hair, straight hair, red eyes, black hoodie, white pleated skirt"
negativo = "monochrome, 3d"
notas = "Free text, not used in the prompt."

[[loras]]
nome = "my_character_v1"
peso = 0.9
```

| Field | Type | Default | Meaning |
|---|---|---|---|
| `versao_ficha` | 1 | 1 | Format version |
| `nome` | text | required | The character's name (the web interface names the file after it: lower case, no accents) |
| `tags` | text | `""` | Tags that describe the character, comma-separated, with AUTOMATIC1111 weights |
| `negativo` | text | `""` | Negative tags for this character |
| `notas` | text | `""` | Notes; not used in the prompt |
| `loras` | list of tables | none | `nome` (a file in the LoRA folder) and `peso` (-4 to 4, default 1) |

Unknown fields are refused. In a request, `"ficha": "exemplo"` looks up `personagens/exemplo.toml`; a value ending in
`.toml` or containing `/` is a path. The prompt order is: quality tags, style tags, rating tags, the sheet's tags, the
scene prompt, without repeated tags (so the sheet does not need `source_anime`). For a LoRA in both the sheet and the
request, the request's weight wins.

An example sheet is in [examples/personagens/exemplo.toml](../examples/personagens/exemplo.toml).
