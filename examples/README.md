# Examples

[Back to the README](../README.md)

| File | What it is |
|---|---|
| `pedido.json` | A generation request (format in [docs/contrato.md](../docs/contrato.md)) that uses the example character sheet, with hires fix and face fix on |
| `personagens/exemplo.toml` | A character sheet (format in [docs/fichas.md](../docs/fichas.md)) for a generic original character |

Run the request from the repository root (the sheet path in it is relative to the current folder):
```
bin/aigen.sh --pedido examples/pedido.json saida/exemplo.png
```
The automated tests read both files to check the formats; they never generate an image.
