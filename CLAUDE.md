@AGENTS.md

# Claude Code

Rules for a Claude Code agent in this repository, on top of `AGENTS.md`.

## No image work: images are the owner's job
- **Never generate an image.** Do not run `bin/aigen.sh`, `bin/aigen_batch.sh`, `bin/aigen_web.sh` or
  `bin/open_web.sh` (nor the desktop shortcut), nor `aigen.generate`, `aigen.batch` or `aigen.web` in any other way,
  nor any script that loads a checkpoint, to "try" or "check" a change. There are no image tests: not as automated
  tests, not as manual checks.
- **Never look at an image.** Do not open, read, view or describe PNG, JPG, WEBP or GIF files (the outputs, the
  examples or any other), and do not inspect their pixels with a script.
- **Never take screenshots** and never open the web interface in a browser.
- `.claude/settings.json` denies these commands and image reads; the rule holds even where a pattern does not catch
  a command.
- When a change affects the images (a stage, a default, the prompt assembly), say so plainly and say what the owner
  should look at when they run it. Do not claim an image got better or worse.

## The repository is public
- Follow "Public repository" in `AGENTS.md`. Never stage images, outputs, reports, logs, weights, sheets of real
  characters or anything with a path or name from this machine.
- Before every commit, look at what is staged (`git status --short` and `git diff --cached --stat`), not only at
  what you meant to change, and run `python3 bin/check_secrets.py --all` and `tests/run.sh`.
- Commit messages, branch names, pull requests and issues are public too: describe the change, never the owner's
  private projects, characters, prompts or images.

## What to run
- The tests: `tests/run.sh`, `python3 tests/test_contract.py` and `python3 tests/test_pure.py` (seconds, no GPU).
- Do not install the environment (`bin/install.sh`, `uv sync`), download models (`bin/download_extras.sh`) or
  start anything on the GPU unless the owner asks for it in this conversation.
