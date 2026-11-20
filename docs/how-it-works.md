# How it works

[Back to the README](../README.md)

A generation is a sequence of stages that share one *job* (`generate.Job`). Each stage declares what it reads from
the job and what it writes to it (`@stages.declare`), and the whole sequence is checked before the first stage runs
(`stages.check`): a stage that reads something no earlier stage writes stops the run before anything is loaded on
the GPU.

1. **Request check** (`generate.check_request`). Everything that can be checked without loading the model: the Python
   libraries, the checkpoint file, the upscaler and face detector files (only when hires fix or face fix is on), the
   character sheet, every LoRA file and the output paths. A problem here ends with exit code 2 and nothing loaded or
   written.
2. **Prompt** (`prompts.stage`). The positive prompt is, in this order: the Pony quality tags
   (`score_9, score_8_up, ...`, unless `"quality": false`), the style's source tag (`source_anime`, unless
   `"style": null`), `rating_safe` (unless `"block_explicit": false`), the sheet's tags and the request's prompt,
   joined without repeated tags (the first occurrence wins; case and extra spaces do not count). The negative prompt
   is built the same way: `score_6, score_5, score_4`, then `source_cartoon, source_furry, source_pony, 3d, realistic,
   photorealistic`, then `rating_questionable, rating_explicit`, then the sheet's and the request's negatives. Pony
   was trained with these source and rating tags; without them it mixes styles and drifts towards explicit content.
   The sheet's LoRAs and the request's are merged; for the same name, the request's weight wins.
3. **Model** (`model.stage`). The SDXL checkpoint is loaded once per session (`model.Session`) in fp16 on the GPU
   (fp32 on the CPU), with `StableDiffusionXLPipeline.from_single_file`. Each request sets its own sampler.
4. **LoRAs** (`loras.stage`). LoRAs are loaded as PEFT adapters and kept in the session; they are reloaded only when
   the list of names changes, and the weights are set on every request.
5. **Generation** (`generation.stage`). Text to image at the request's width and height. The prompt goes through
   [compel](https://github.com/damian0815/compel), which handles weights and prompts longer than 77 tokens. Weights
   are written in the AUTOMATIC1111 syntax (`(tag:1.2)`, `(tag)`, `[tag]`, `\(` for a literal parenthesis) and
   translated to compel's syntax by `prompts.to_compel`. diffusers' SDXL already uses the penultimate layer of the
   text encoders, which is the "CLIP skip 2" Pony asks for. The seed drives a `torch.Generator` on the GPU. Images
   above 1.25 megapixels are decoded by the VAE in tiles (the SDXL VAE decodes in fp32, and a large image decoded at
   once does not fit in 16 GB); Pony's usual sizes (about 1 megapixel) are decoded at once. Each request first puts
   the VAE back in the pipeline's type, so a decode that failed half-way (with the VAE left in fp32) does not break
   the next requests.
6. **Hires fix** (`hires.stage`, off by default). The image is enlarged by `scale` (to a multiple of 8): with the
   upscaler model (RealESRGAN anime 6B by default, loaded through [spandrel](https://github.com/chaiNNer-org/spandrel))
   and then Lanczos to the exact size, or with Lanczos only. Then an image-to-image pass with strength `strength`
   redraws the details. diffusers runs `int(steps × strength)` of the steps it is given, so the pass asks for
   `ceil(steps / strength)` steps to run `steps` of them. The VAE decodes in tiles when the new size is above 1.25
   megapixels.
7. **Face fix** (`face.stage`, off by default). Faces are found with an OpenCV cascade trained on anime faces
   (`lbpcascade_animeface`); faces smaller than 4 % of the shorter side are ignored, and at most `max_faces` are
   kept, largest first. Each face gets a square crop with `margin` (a fraction of the face size) on each side, clamped
   to the image. The crop is resized to 1024 px, inpainted with strength `strength` (mask: the face box with a soft
   edge), resized back and pasted with the same mask. `prompt` adds tags for the face only. Each face uses seed + n.
8. **Output** (`output.stage`). The PNG and the `.aigen.json` report are created in exclusive mode: an existing file
   is never overwritten, even by two runs at the same time. See [contract.md](contract.md) for both formats.

With `count` > 1, the sequence runs once per image, with consecutive seeds, on the same session.

## The stages in the code

The table below is the one the stages declare (with hires fix and face fix on), checked by `tests/test_contract.py`.
The names in `stages.BASE` (`request`, `output`, `session`, `cfg`, `t_start`, `timings`) come with the job.

| Stage | Reads | Writes |
|---|---|---|
| `generate.check_request` | `cfg`, `output`, `request` | `report`, `sheet` |
| `prompts.stage` | `report`, `request`, `sheet` | `loras`, `negative`, `positive` |
| `model.stage` | `request`, `session` | `pipe` |
| `loras.stage` | `cfg`, `loras`, `pipe`, `report`, `session` | `active_loras` |
| `generation.stage` | `active_loras`, `negative`, `pipe`, `positive`, `report`, `request`, `session` | `image` |
| `hires.stage` | `active_loras`, `image`, `negative`, `pipe`, `positive`, `report`, `request`, `session` | `image` |
| `face.stage` | `active_loras`, `image`, `negative`, `pipe`, `positive`, `report`, `request`, `session` | `faces`, `image` |
| `output.stage` | `active_loras`, `cfg`, `image`, `negative`, `output`, `positive`, `report`, `request` | `files` |

## Modules

| Module | Role | Needs the GPU libraries |
|---|---|---|
| `generate.py` | The program: options, the job, the sequence, `run` | no (the stages import them) |
| `batch.py` | Batch mode | no |
| `web.py` | The web interface (Gradio) | Gradio, inside its functions |
| `contract.py` | Format versions, exit codes, the request check | no (pure) |
| `stages.py` | Stage declarations and the sequence check | no (pure) |
| `config.py` | `config.ini`, `config.local.ini` and the `AIGEN_*` variables | no (pure) |
| `prompts.py` | Prompt assembly and the weight syntax | no (pure) |
| `sheets.py` | Character sheets (TOML) | no (pure) |
| `loras.py` | LoRA files and the `name:weight` list | only the stage |
| `metadata.py` | The PNG text chunks | no (pure) |
| `model.py` | The session: pipeline, compel, upscaler, face detector, samplers | yes, inside its functions |
| `generation.py`, `hires.py`, `face.py`, `output.py` | The GPU stages and the output | yes, inside the stages |

No module imports torch, diffusers, Gradio or another heavy library at the top of the file (checked by
`tests/test_contract.py`), so every module imports, and every test runs, without them.
