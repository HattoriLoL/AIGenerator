"""The web interface (Gradio): a layer over generate.run, which listens only on 127.0.0.1.

    bin/aigen_web.sh [--port N]

Tabs: Generate (the request, the sheets, the LoRAs, the hires fix and the face fix), Sheets (create and edit), Gallery
(the images of the output folder) and Read PNG (rebuilds the request from an AIGenerator image). One generation at a
time. Each failure goes, with the full error and the request, to the log <output folder>/aigen-web.log; in private
mode (the "private" box of the Generate tab, which starts as the config's [privacy] save_prompts says) neither the
PNG, the report nor the log keeps the prompts.
gradio and PIL are only imported inside the functions.
"""
import datetime
import json
import os
import sys
import threading
import traceback

from aigen import VERSION, config, contract, generate, loras, metadata, model, sheets

NO_SHEET = "(none)"
NO_STYLE = "none"
FIELDS = ("sheet", "prompt", "negative", "quality", "style", "block_explicit", "width", "height", "steps", "cfg",
          "sampler", "seed", "count", "loras", "hires", "hires_scale", "hires_strength", "hires_steps",
          "hires_upscaler", "face_fix", "face_fix_strength", "face_fix_steps", "face_fix_margin", "face_fix_prompt",
          "face_fix_max")
GALLERY_MAX = 60
LOG = "aigen-web.log"


def log_failure(folder, request, error_text, now=None, private=False):
    """Appends the time, the request (not in private mode) and the full error (the traceback) to the output folder's
    log; returns its path."""
    now = now or datetime.datetime.now()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, LOG)
    lines = ["=== " + now.isoformat(timespec="seconds")]
    if not private:
        lines.append("request: " + json.dumps(request, ensure_ascii=False, sort_keys=True))
    lines.append(error_text.rstrip())
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def private_default(cfg):
    """The initial value of the Generate tab's "private" box: ticked when the config does not save the prompts."""
    return not cfg.save_prompts


def split_values(values):
    """The Generate button's values: the form ({field of FIELDS: value}) and, after them, the "private" box (an output
    option of that generation, not a request field)."""
    return dict(zip(FIELDS, values[:len(FIELDS)])), bool(values[len(FIELDS)])


def request_from_form(v):
    """The normalized request from the form values ({field of FIELDS: value})."""
    request = {"prompt": v["prompt"] or "", "negative": v["negative"] or "",
               "sheet": None if v["sheet"] in (None, "", NO_SHEET) else v["sheet"], "quality": bool(v["quality"]),
               "style": None if v["style"] in (None, "", NO_STYLE) else v["style"],
               "block_explicit": bool(v["block_explicit"]), "width": int(v["width"]),
               "height": int(v["height"]), "steps": int(v["steps"]),
               "cfg": float(v["cfg"]), "sampler": v["sampler"], "seed": int(v["seed"]),
               "count": int(v["count"]), "loras": loras.parse_list(v["loras"])}
    if v["hires"]:
        request["hires"] = {"scale": float(v["hires_scale"]), "strength": float(v["hires_strength"]),
                            "steps": int(v["hires_steps"]), "upscaler": v["hires_upscaler"]}
    if v["face_fix"]:
        request["face_fix"] = {"strength": float(v["face_fix_strength"]), "steps": int(v["face_fix_steps"]),
                               "margin": float(v["face_fix_margin"]), "prompt": v["face_fix_prompt"] or "",
                               "max_faces": int(v["face_fix_max"])}
    return contract.normalize(request, "the request from the form")


def form_from_request(request):
    """The form values ({field: value}) of a normalized request (the reverse of request_from_form)."""
    h = request["hires"] or {k: c[2] for k, c in contract.HIRES_FIELDS.items()}
    f = request["face_fix"] or {k: c[2] for k, c in contract.FACE_FIELDS.items()}
    v = {k: request[k] for k in ("prompt", "negative", "quality", "width", "height", "steps", "cfg", "sampler",
                                 "seed", "count")}
    v.update(style=request["style"] or NO_STYLE, block_explicit=request["block_explicit"])
    v.update(sheet=request["sheet"] or NO_SHEET, hires=bool(request["hires"]), face_fix=bool(request["face_fix"]),
             loras="\n".join("%s:%g" % (l["name"], l["weight"]) for l in request["loras"]))
    v.update({"hires_" + k: h[k] for k in ("scale", "strength", "steps", "upscaler")})
    v.update({"face_fix_" + k: f[k] for k in ("strength", "steps", "margin", "prompt")}, face_fix_max=f["max_faces"])
    return v


def new_path(folder, now):
    """folder/YYYY-MM-DD/HHMMSS.png, with _2, _3 ... if a PNG (or an x_001.png series) with that name exists."""
    day = os.path.join(folder, now.strftime("%Y-%m-%d"))
    base = os.path.join(day, now.strftime("%H%M%S"))
    n, candidate = 1, base
    while any(os.path.exists(candidate + s) for s in (".png", "_001.png")):
        n += 1
        candidate = "%s_%d" % (base, n)
    return candidate + ".png"


def recent(folder, n=GALLERY_MAX):
    """The n newest PNGs of the output folder (and its subfolders)."""
    found = []
    for dirpath, _, names in os.walk(folder):
        found += [os.path.join(dirpath, x) for x in names if x.lower().endswith(".png")]
    return sorted(found, key=os.path.getmtime, reverse=True)[:n]


def png_texts(path):
    from PIL import Image
    with Image.open(path) as im:
        return dict(getattr(im, "text", {}) or im.info)


class App:
    """The interface state: the configuration, the session (the loaded model) and the lock of one generation at a
    time."""

    def __init__(self, cfg):
        self.cfg, self.session, self.lock = cfg, model.Session(cfg), threading.Lock()

    def sheet_choices(self):
        return [NO_SHEET] + sheets.list_sheets(self.cfg.sheets_folder)

    def generate(self, *values):
        import gradio as gr
        form, private = split_values(values)
        try:
            request = request_from_form(form)
        except contract.RequestError as e:
            raise gr.Error(str(e))
        if not self.lock.acquire(blocking=False):
            raise gr.Error("a generation is already running; wait for it to finish")
        try:
            done = generate.run(request, new_path(self.cfg.output_folder, datetime.datetime.now()), self.session,
                                self.cfg, private=private)
        except contract.RequestError as e:
            raise gr.Error(str(e))
        except Exception as e:  # the model did not load, the GPU ran out of memory, ...
            text = traceback.format_exc()
            print(text, file=sys.stderr)
            log = log_failure(self.cfg.output_folder, request, text, private=private)
            model.empty_cache()  # after running out of memory, the next generation starts with a clean GPU
            raise gr.Error("the generation failed: %s: %s (details in %s)" % (type(e).__name__, e, log))
        finally:
            self.lock.release()
        pngs = [png for png, _ in done]
        return pngs, "Written: " + ", ".join("`%s`" % os.path.relpath(p, self.cfg.output_folder) for p in pngs)

    def read_png(self, path):
        import gradio as gr
        if not path:
            raise gr.Error("choose a PNG")
        try:
            v = form_from_request(metadata.request_from_png(png_texts(path)))
        except contract.RequestError as e:
            raise gr.Error(str(e))
        except OSError as e:
            raise gr.Error("the file did not open as a PNG: %s" % e)
        return [v[c] for c in FIELDS]

    def open_sheet(self, name):
        import gradio as gr
        if name in (None, "", NO_SHEET):
            return "", "", "", "", ""
        try:
            s = sheets.read_sheet(sheets.resolve(name, self.cfg.sheets_folder))
        except contract.RequestError as e:
            raise gr.Error(str(e))
        return (s["name"], s["tags"], s["negative"], "\n".join("%s:%g" % (l["name"], l["weight"]) for l in s["loras"]),
                s["notes"])

    def save_sheet(self, name, tags, negative, loras_text, notes, overwrite):
        import gradio as gr
        try:
            sheet = {"name": name or "", "tags": tags or "", "negative": negative or "", "notes": notes or "",
                     "loras": loras.parse_list(loras_text)}
            path = os.path.join(self.cfg.sheets_folder, sheets.file_name(name or "") + ".toml")
            sheets.write_sheet(sheet, path, overwrite=bool(overwrite))
        except contract.RequestError as e:
            raise gr.Error(str(e))
        choices = self.sheet_choices()
        return ("Sheet saved: `%s`" % os.path.basename(path), gr.update(choices=choices),
                gr.update(choices=choices))


def _generate_tab(gr, app, c):
    with gr.Row():
        with gr.Column(scale=3):
            c["sheet"] = gr.Dropdown(app.sheet_choices(), value=NO_SHEET, label="Character sheet",
                                     allow_custom_value=True)
            c["prompt"] = gr.Textbox(label="Prompt (scene tags)", lines=4)
            c["negative"] = gr.Textbox(label="Negative", lines=2)
            with gr.Row():
                c["quality"] = gr.Checkbox(True, label="Pony quality tags (score_9, score_8_up, ...)")
                c["block_explicit"] = gr.Checkbox(True, label="Block explicit ratings (rating_safe)")
                c["style"] = gr.Dropdown(list(contract.STYLES) + [NO_STYLE], value="anime", label="Style")
            with gr.Row():
                c["width"] = gr.Slider(contract.SIDE_MIN, contract.SIDE_MAX, 1024, step=8, label="Width")
                c["height"] = gr.Slider(contract.SIDE_MIN, contract.SIDE_MAX, 1024, step=8, label="Height")
            with gr.Row():
                c["steps"] = gr.Slider(1, 150, 25, step=1, label="Steps")
                c["cfg"] = gr.Slider(1, 30, 7, step=0.5, label="CFG")
            with gr.Row():
                c["sampler"] = gr.Dropdown(list(contract.SAMPLERS), value="euler_a", label="Sampler")
                c["seed"] = gr.Number(-1, precision=0, label="Seed (-1 draws one)")
                c["count"] = gr.Slider(1, 16, 1, step=1, label="Count")
            c["loras"] = gr.Textbox(label="LoRAs (one per line, name:weight)", lines=2,
                                    info="In the folder: " + (", ".join(loras.list_loras(app.cfg.loras_folder))
                                                              or "none"))
            _extras(gr, c)
            c["private"] = gr.Checkbox(private_default(app.cfg), label="Don't save the prompt (private)",
                                       info="The PNG gets no metadata, and the report and the error log leave out the"
                                            " prompts, the sheet and the LoRAs")
            button = gr.Button("Generate", variant="primary")
        with gr.Column(scale=2):
            result = gr.Gallery(label="Result", columns=2, height="auto")
            notice = gr.Markdown()
    return button, result, notice


def _extras(gr, c):
    with gr.Accordion("Hires fix (off by default)", open=False):
        c["hires"] = gr.Checkbox(False, label="Turn on")
        with gr.Row():
            c["hires_scale"] = gr.Slider(1.05, 4, 1.5, step=0.05, label="Scale")
            c["hires_strength"] = gr.Slider(0.05, 1, 0.4, step=0.05, label="Strength")
            c["hires_steps"] = gr.Slider(1, 150, 15, step=1, label="Steps")
        c["hires_upscaler"] = gr.Radio(list(contract.UPSCALERS), value="model", label="Upscaler")
    with gr.Accordion("Face fix (off by default)", open=False):
        c["face_fix"] = gr.Checkbox(False, label="Turn on")
        with gr.Row():
            c["face_fix_strength"] = gr.Slider(0.05, 1, 0.4, step=0.05, label="Strength")
            c["face_fix_steps"] = gr.Slider(1, 150, 20, step=1, label="Steps")
            c["face_fix_margin"] = gr.Slider(0, 2, 0.3, step=0.05, label="Margin")
            c["face_fix_max"] = gr.Slider(1, 16, 4, step=1, label="Maximum faces")
        c["face_fix_prompt"] = gr.Textbox(label="Extra tags for the face")


def _sheets_tab(gr, app):
    choice = gr.Dropdown(app.sheet_choices(), value=NO_SHEET, label="Open a sheet")
    name = gr.Textbox(label="Character name")
    tags = gr.Textbox(label="Tags (what describes the character: hair, eyes, outfit)", lines=3)
    negative = gr.Textbox(label="Negative", lines=2)
    loras_text = gr.Textbox(label="LoRAs (one per line, name:weight)", lines=2)
    notes = gr.Textbox(label="Notes", lines=2)
    overwrite = gr.Checkbox(False, label="Overwrite if it already exists")
    save = gr.Button("Save sheet")
    notice = gr.Markdown()
    choice.change(app.open_sheet, choice, [name, tags, negative, loras_text, notes])
    return choice, save, [name, tags, negative, loras_text, notes, overwrite], notice


def build(app):
    """Builds the interface (gr.Blocks) of the App."""
    import gradio as gr
    c = {}
    with gr.Blocks(title="AIGenerator") as page:
        gr.Markdown("# AIGenerator\nPony Diffusion XL · version %s" % VERSION)
        with gr.Tab("Generate"):
            button, result, notice = _generate_tab(gr, app, c)
        with gr.Tab("Sheets"):
            choice, save, sheet_inputs, sheet_notice = _sheets_tab(gr, app)
        with gr.Tab("Gallery"):
            refresh = gr.Button("Refresh")
            gallery = gr.Gallery(label="Output folder", columns=4, height="auto")
        with gr.Tab("Read PNG"):
            upload = gr.File(label="A PNG made by AIGenerator", file_types=[".png"], type="filepath")
            gr.Markdown("The request kept in the PNG goes to the Generate tab. A PNG made in private mode has none.")
        inputs = [c[k] for k in FIELDS]
        button.click(app.generate, inputs + [c["private"]], [result, notice], concurrency_limit=1)
        save.click(app.save_sheet, sheet_inputs, [sheet_notice, c["sheet"], choice])
        refresh.click(lambda: recent(app.cfg.output_folder), None, gallery)
        upload.upload(app.read_png, upload, inputs)
    return page


def main(argv=None):
    p = generate._Options(prog=contract.command("aigen_web"), description="The AIGenerator web interface.")
    p.add_argument("--port", type=int, help="the port (default: the one in the config, 7860)")
    p.add_argument("--open", action="store_true", help="open the interface in the browser when it is ready")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.read()
        model.check_libraries(model.LIBRARIES + ("gradio",))
    except contract.RequestError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return contract.BAD_REQUEST
    port = a.port or cfg.port
    print("AIGenerator %s at http://127.0.0.1:%d" % (VERSION, port))
    build(App(cfg)).queue().launch(server_name="127.0.0.1", server_port=port, inbrowser=a.open)
    return contract.OK


if __name__ == "__main__":
    sys.exit(main())
