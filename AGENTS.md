# AGENTS.md

Conventions for anyone working on this repository, person or coding agent. How to use the tool is in the
`README.md`; each topic in detail is in `docs/`.

## What it is
An image generator for anime characters on top of Pony Diffusion XL (SDXL), with diffusers: a request (JSON or
command-line options) goes in; a PNG with its metadata and a JSON report come out. The core is the command line
(`aigen/gerar.py`); the batch mode (`aigen/lote.py`) and the web interface (`aigen/web.py`, Gradio, local only) are
thin layers over the same `gerar.rodar`.

## Folders
| Folder | Contents | When to change it |
|---|---|---|
| `aigen/` | The code. `gerar.py` is the program (the options, the job and the sequence of stages); the stages are `gerar.conferir_pedido`, `prompts.py`, `modelo.py`, `loras.py`, `geracao.py`, `hires.py`, `rosto.py` and `saida.py` (see `docs/como-funciona.md`); `contrato.py`, `etapas.py`, `config.py`, `fichas.py` and `metadados.py` are pure shared parts; `lote.py` and `web.py` are the other entry points | A change in behavior |
| `bin/` | The launchers (`aigen.sh`, `aigen_lote.sh`, `aigen_web.sh`, and `abrir_web.sh` for the desktop shortcut), the Python lookup (`_python.sh`), the installers (`instalar.sh`, `instalar_atalho.sh`), `baixar_auxiliares.sh` and `verificar_segredos.py` | A change in how the tool is called or installed |
| `tests/` | The automated tests | Every change in behavior |
| `examples/` | An example request and character sheet, read by the tests | When a new test needs another case |
| `docs/` | The documentation, one file per topic | When the behavior changes |
| `.githooks/` | The `pre-push` hook ("Before pushing") | When a check is added |
| `.claude/settings.json` | What a Claude Code agent may run here without asking (the tests) and what it may never do (generate or open images) | When a test or launcher command changes |

## Running
```
bin/aigen.sh output.png [options]
bin/aigen_lote.sh requests_folder output_folder
bin/aigen_web.sh
```
The launchers find Python through the `AIGEN_PYTHON` variable or the `.venv/` that `bin/instalar.sh` creates. The
model paths come from the `AIGEN_*` variables, `config.local.ini` (ignored by git) or `config.ini`. The versioned
`config.ini` is only a template: a machine's paths go in `config.local.ini` or in the variables, never in a
versioned file.

## Testing
| | Command | What it runs | When |
|---|---|---|---|
| **Contract** | `python3 tests/test_contrato.py` | the request contract, the exit codes, the code rules, the launchers, the docs that are checked against the code and the isolation check | before every commit, and on every push (through the hook) |
| **Pure modules** | `python3 tests/test_puros.py` | prompts and weights, sheets, LoRA lists, metadata, config, the stage sequences of each mode, the face-box math and the web interface's conversions | before every commit, and on every push (through the hook) |
| **All** | `tests/run.sh` | both | before every commit that touches `aigen/` or `bin/` |

They need any Python 3.11+ and nothing else: no PyTorch, no GPU, no model. **No automated test generates, opens or
compares an image.** Whether an image is good is judged by a person, by running the tool; a change that affects the
images is described in the pull request so the owner can check it.

- New behavior gets a case in `tests/test_puros.py` (or in `tests/test_contrato.py` when it is part of the contract
  or a repository rule).
- Code that needs the GPU libraries stays small and inside the stages; the decisions (sizes, boxes, step counts,
  prompt text, file names) go into pure functions that the tests cover.

## Before pushing
Every clone enables the hook once:
```
git config core.hooksPath .githooks
```
On every `git push`, for the commits the remote does not have yet, `.githooks/pre-push` looks for secrets in each
commit (`bin/verificar_segredos.py`) and, on a copy of the pushed commit's tree, checks the syntax of every `.py` and
runs `tests/test_contrato.py` and `tests/test_puros.py`. If anything fails, the push is blocked. **Do not bypass it
with `--no-verify`**: fix it and push again. A false positive of the secret scanner, once checked, is released with
the text `scan-secrets: ok` on that line, amending the commit that brought it (each commit is read on its own).

## What must not break
- **No output is overwritten.** An existing PNG or report is refused before anything is loaded; the files are created
  in exclusive mode.
- **Every PNG carries its request** (the `aigen` chunk) and the AUTOMATIC1111 `parameters` text, and the request in
  it, given back to the tool, makes the same image (within GPU nondeterminism, `docs/limitacoes.md`).
- **The contract** ([docs/contrato.md](docs/contrato.md), checked by `aigen/contrato.py` and `aigen/fichas.py`) is what
  other programs and the user's saved files rely on: the request (`versao_pedido`), the character sheet
  (`versao_ficha`), the outputs (`versao_formato`) and the exit codes. A field that changes meaning or is removed
  raises the format version; a new optional field does not.
- **The exit codes follow one rule**, in `gerar.py` and `lote.py`: **0** success; **1** an image could not be made
  (the model did not load, a stage failed; in batch mode, some request failed); **2** the request is wrong and
  nothing was loaded or written. Every error message starts with `ERRO:`.
- **The stage sequence is checked before it runs** (`etapas.conferir`), and the stage table in
  `docs/como-funciona.md` is the one the stages declare (checked by a test).

## Isolation: AIGenerator knows no project that uses it
- **Nothing project-specific goes into the repository**: not the name of a game, a character, a tool or a private
  repository; not a value taken from one project as a default; not a path from someone's machine. This covers the
  code, the messages, the tests, the examples, the docs, the commit messages and the pull requests. Examples use
  generic original characters only.
- **What a project needs enters through the contract**: a request field or a command-line option, off by default.
- **The denylist.** Each owner keeps the private terms that must never show up here (project names, folder names,
  paths) in `.aigen-proibidos`, in the root, one term per line (case-insensitive, `#` comments). It is ignored by git
  and the secret scanner refuses it by name. `tests/test_contrato.py` (class `Isolamento`), and with it the pre-push
  hook, fails when a term appears in a versioned file name or text, or in the author, message or added lines of a
  commit no remote has yet. Without the file the check is skipped.
- Widening what may enter is the repository owner's decision, never something done in passing within another change.

## Rules
- **The repository is in English.** Docs, `README.md`, this file, `CLAUDE.md`, commit messages, branch names, pull
  requests and issues are in English. The interface stays in Portuguese for now: the code (names and comments), the
  command-line options, the `ERRO:` messages, the web interface's labels and the JSON and TOML fields. A change
  keeps the language of the file it touches, and renaming an option, a message or a field is a contract change (see
  "What must not break").
- New functionality comes in as an option that is off by default. The default behavior changes only with the
  owner's approval, after they have compared the images.
- A change in behavior changes the docs in `docs/` in the same commit.
- Only libraries and default models whose license allows commercial use. Nothing research-only or non-commercial as
  a default. Every dependency in `pyproject.toml` has a row in `docs/licencas.md` (checked by a test).
- **No model weights in the repository** (`.safetensors`, `.ckpt`, `.pt`, `.pth`, ...): the secret scanner refuses
  them by name. Models are downloaded by each user.
- Heavy libraries (torch, diffusers, transformers, compel, PIL, numpy, OpenCV, spandrel, Gradio) are imported inside
  the functions that use them, never at the top of a module (checked by a test), so every module imports without
  them.
- No function over 80 lines and no import cycle in `aigen/` (checked by a test).
- The web interface listens only on `127.0.0.1`.
- Commits carry no AI co-authorship or signature.
- Commit, push and merge only with the repository owner's authorization: a request from them, or a workflow they
  started that says what it may do. Always on a branch and through a pull request; never directly on `main`, never
  with `--force`.
