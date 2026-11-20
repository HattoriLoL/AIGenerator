# How it works

[Back to the README](../README.md)

A generation is a sequence of stages that share one *job* (`gerar.Trabalho`). Each stage declares what it reads from
the job and what it writes to it (`@etapas.declarar`), and the whole sequence is checked before the first stage runs
(`etapas.conferir`): a stage that reads something no earlier stage writes stops the run before anything is loaded on
the GPU.

1. **Request check** (`gerar.conferir_pedido`). Everything that can be checked without loading the model: the Python
   libraries, the checkpoint file, the upscaler and face detector files (only when hires fix or face fix is on), the
   character sheet, every LoRA file and the output paths. A problem here ends with exit code 2 and nothing loaded or
   written.
2. **Prompt** (`prompts.etapa`). The positive prompt is, in this order: the Pony quality tags
   (`score_9, score_8_up, ...`, unless `"qualidade": false`), the style's source tag (`source_anime`, unless
   `"estilo": null`), `rating_safe` (unless `"bloquear_explicito": false`), the sheet's tags and the request's prompt,
   joined without repeated tags (the first occurrence wins; case and extra spaces do not count). The negative prompt
   is built the same way: `score_6, score_5, score_4`, then `source_cartoon, source_furry, source_pony, 3d, realistic,
   photorealistic`, then `rating_questionable, rating_explicit`, then the sheet's and the request's negatives. Pony
   was trained with these source and rating tags; without them it mixes styles and drifts towards explicit content. The sheet's LoRAs and the request's are merged; for the same name, the request's
   weight wins.
3. **Model** (`modelo.etapa`). The SDXL checkpoint is loaded once per session (`modelo.Sessao`) in fp16 on the GPU
   (fp32 on the CPU), with `StableDiffusionXLPipeline.from_single_file`. Each request sets its own sampler.
4. **LoRAs** (`loras.etapa`). LoRAs are loaded as PEFT adapters and kept in the session; they are reloaded only when
   the list of names changes, and the weights are set on every request.
5. **Generation** (`geracao.etapa`). Text to image at the request's width and height. The prompt goes through
   [compel](https://github.com/damian0815/compel), which handles weights and prompts longer than 77 tokens. Weights
   are written in the AUTOMATIC1111 syntax (`(tag:1.2)`, `(tag)`, `[tag]`, `\(` for a literal parenthesis) and
   translated to compel's syntax by `prompts.para_compel`. diffusers' SDXL already uses the penultimate layer of the
   text encoders, which is the "CLIP skip 2" Pony asks for. The seed drives a `torch.Generator` on the GPU. Images
   above 1.25 megapixels are decoded by the VAE in tiles (the SDXL VAE decodes in fp32, and a large image decoded at
   once does not fit in 16 GB); Pony's usual sizes (about 1 megapixel) are decoded at once. Each request first puts
   the VAE back in the pipeline's type, so a decode that failed half-way (with the VAE left in fp32) does not break
   the next requests.
6. **Hires fix** (`hires.etapa`, off by default). The image is enlarged by `escala` (to a multiple of 8): with the
   upscaler model (RealESRGAN anime 6B by default, loaded through [spandrel](https://github.com/chaiNNer-org/spandrel))
   and then Lanczos to the exact size, or with Lanczos only. Then an image-to-image pass with strength `forca` redraws
   the details. diffusers runs `int(steps × strength)` of the steps it is given, so the pass asks for
   `ceil(passos / forca)` steps to run `passos` of them. The VAE decodes in tiles when the new size is above 1.25
   megapixels.
7. **Face fix** (`rosto.etapa`, off by default). Faces are found with an OpenCV cascade trained on anime faces
   (`lbpcascade_animeface`); faces smaller than 4 % of the shorter side are ignored, and at most `max_rostos` are
   kept, largest first. Each face gets a square crop with `margem` (a fraction of the face size) on each side, clamped
   to the image. The crop is resized to 1024 px, inpainted with strength `forca` (mask: the face box with a soft
   edge), resized back and pasted with the same mask. `prompt` adds tags for the face only. Each face uses seed + n.
8. **Output** (`saida.etapa`). The PNG and the `.aigen.json` report are created in exclusive mode: an existing file
   is never overwritten, even by two runs at the same time. See [contrato.md](contrato.md) for both formats.

With `quantidade` > 1, the sequence runs once per image, with consecutive seeds, on the same session.

## The stages in the code

The table below is the one the stages declare (with hires fix and face fix on), checked by `tests/test_contrato.py`.
The names in `etapas.BASE` (`pedido`, `saida`, `sessao`, `cfg`, `t_ini`, `tempos`) come with the job.

| Stage | Reads | Writes |
|---|---|---|
| `gerar.conferir_pedido` | `cfg`, `pedido`, `saida` | `ficha`, `rel` |
| `prompts.etapa` | `ficha`, `pedido`, `rel` | `loras`, `negativo`, `positivo` |
| `modelo.etapa` | `pedido`, `sessao` | `pipe` |
| `loras.etapa` | `cfg`, `loras`, `pipe`, `rel`, `sessao` | `loras_ativas` |
| `geracao.etapa` | `loras_ativas`, `negativo`, `pedido`, `pipe`, `positivo`, `rel`, `sessao` | `imagem` |
| `hires.etapa` | `imagem`, `loras_ativas`, `negativo`, `pedido`, `pipe`, `positivo`, `rel`, `sessao` | `imagem` |
| `rosto.etapa` | `imagem`, `loras_ativas`, `negativo`, `pedido`, `pipe`, `positivo`, `rel`, `sessao` | `imagem`, `rostos` |
| `saida.etapa` | `cfg`, `imagem`, `loras_ativas`, `negativo`, `pedido`, `positivo`, `rel`, `saida` | `arquivos` |

## Modules

| Module | Role | Needs the GPU libraries |
|---|---|---|
| `gerar.py` | The program: options, the job, the sequence, `rodar` | no (the stages import them) |
| `lote.py` | Batch mode | no |
| `web.py` | The web interface (Gradio) | Gradio, inside its functions |
| `contrato.py` | Format versions, exit codes, the request check | no (pure) |
| `etapas.py` | Stage declarations and the sequence check | no (pure) |
| `config.py` | `config.ini`, `config.local.ini` and the `AIGEN_*` variables | no (pure) |
| `prompts.py` | Prompt assembly and the weight syntax | no (pure) |
| `fichas.py` | Character sheets (TOML) | no (pure) |
| `loras.py` | LoRA files and the `nome:peso` list | only the stage |
| `metadados.py` | The PNG text chunks | no (pure) |
| `modelo.py` | The session: pipeline, compel, upscaler, face detector, samplers | yes, inside its functions |
| `geracao.py`, `hires.py`, `rosto.py`, `saida.py` | The GPU stages and the output | yes, inside the stages |

No module imports torch, diffusers, Gradio or another heavy library at the top of the file (checked by
`tests/test_contrato.py`), so every module imports, and every test runs, without them.
