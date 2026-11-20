# Examples

[Back to the README](../README.md)

| File | What it is |
|---|---|
| `request.json` | A generation request (format in [docs/contract.md](../docs/contract.md)) that uses the example character sheet, with hires fix and face fix on |
| `characters/example.toml` | A character sheet (format in [docs/sheets.md](../docs/sheets.md)) for a generic original character |

Run the request from the repository root (the sheet path in it is relative to the current folder):
```
bin/aigen.sh --request examples/request.json output/example.png
```
The automated tests read both files to check the formats; they never generate an image.
