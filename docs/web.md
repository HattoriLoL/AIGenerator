# Web interface

[Back to the README](../README.md)

```
bin/aigen_web.sh [--porta N] [--abrir]
```
`--abrir` opens the page in the browser once it is ready.

## Desktop shortcut

`bin/instalar_atalho.sh` adds an "AIGenerator" entry to the application menu (any freedesktop desktop: GNOME, KDE,
...), which can be pinned to the dock. It runs `bin/abrir_web.sh` in a terminal window: if the interface is already
up, it only opens the browser; otherwise it starts the interface there and opens the browser when it is ready.
**Closing that terminal stops the interface and frees the GPU memory** (the checkpoint takes about 7 GB). The
shortcut stores this clone's path, so it is generated on each machine and not versioned.

```
bin/instalar_atalho.sh                 (the system's graphics icon)
bin/instalar_atalho.sh my_icon.svg     (your own icon)
bin/instalar_atalho.sh --remover
```

A [Gradio](https://www.gradio.app/) page at `http://127.0.0.1:7860`. It listens only on this machine (`127.0.0.1`);
there is no login, so do not expose the port. It is a thin layer over the same code as the command line
(`gerar.rodar`): the same request check, the same stages and the same outputs.

| Tab | What it does |
|---|---|
| **Gerar** | The request fields: sheet, prompt, negative, quality tags, the "Desativar classificações explícitas" box (ticked by default: `rating_safe` and no explicit ratings), the style (anime by default), size, steps, CFG, sampler, seed, quantity, LoRAs (one `name:weight` per line; the files found in the LoRA folder are listed below the field), and the hires fix and face fix panels (off by default). The images go to `saida/YYYY-MM-DD/HHMMSS.png` (with `_2`, `_3`, ... when the name is taken), each with its `.aigen.json` report |
| **Fichas** | Open, create and save character sheets ([fichas.md](fichas.md)) in the sheets folder; an existing sheet is overwritten only with the box ticked |
| **Galeria** | The newest 60 PNGs of the output folder |
| **Ler PNG** | Upload a PNG made by AIGenerator: its request (from the `aigen` chunk) fills the Gerar tab, so the image can be made again or varied |

When a generation fails, the page shows the error and the full error (with the request) is appended to
`<output folder>/aigen-web.log`.

The model is loaded on the first generation and stays loaded while the page runs. One generation runs at a time:
clicks made while one runs wait in Gradio's queue.
