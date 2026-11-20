"""The writing: the PNG (with the "parameters" and "aigen" chunks) and the .aigen.json report next to it. No file
that already exists is overwritten. In private mode (t.private) the PNG has no text chunk and the report leaves out
what tells what the image is (docs/contract.md, "The outputs").
"""
import json
import os
import time

from aigen import VERSION, contract, metadata, stages

REPORT_SUFFIX = ".aigen.json"
PRIVATE_REPORT_FIELDS = ("prompt", "sheet", "loras")  # the stage entries of the report left out in private mode


def report_path(png):
    """The report path of a PNG: x.png → x.aigen.json."""
    return os.path.splitext(png)[0] + REPORT_SUFFIX


def paths(output_png, count):
    """The PNGs of a request: `output_png` itself for one image; x_001.png, x_002.png ... for several."""
    if count == 1:
        return [output_png]
    base, ext = os.path.splitext(output_png)
    return ["%s_%03d%s" % (base, i, ext) for i in range(1, count + 1)]


def check_outputs(pngs):
    """Refuses (RequestError) a PNG that does not end in .png and a PNG or report that already exists."""
    for png in pngs:
        if not png.lower().endswith(".png"):
            raise contract.RequestError("the output must end in .png: " + png)
        for c in (png, report_path(png)):
            if os.path.exists(c):
                raise contract.RequestError("the output already exists (nothing is overwritten): " + c)


def build_report(request, entries, png_name, model, seconds, timings, private=False):
    """The dictionary of the .aigen.json report: the request and the stages' entries (sheet, prompt, loras,
    generation, ...). In private mode, the request is redacted (metadata.redact_request) and the prompt, sheet and
    loras entries are left out. Does not change the given values."""
    if private:
        request = metadata.redact_request(request)
        entries = {k: v for k, v in entries.items() if k not in PRIVATE_REPORT_FIELDS}
    return {"format_version": contract.FORMAT_VERSION, "aigen": VERSION, "png": png_name, "request": request,
            "model": model, "seconds": seconds, "timings": dict(timings), **entries, "private": bool(private)}


def report(t, png_name):
    """The .aigen.json report of a job."""
    return build_report(t.request, t.report, png_name, os.path.basename(t.cfg.checkpoint),
                        round(time.time() - t.t_start, 2), t.timings, t.private)


def _write_new(path, write):
    """Creates the file only if it does not exist (mode "x"): two generations at the same time never write over each
    other."""
    with open(path, "xb") as f:
        write(f)


def write_png(image, path, chunks):
    """Writes the image as a new PNG with exactly the given text chunks ({key: text}; none when empty)."""
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    for key, text in chunks.items():
        info.add_text(key, text)
    _write_new(path, lambda f: image.save(f, format="PNG", pnginfo=info))


@stages.declare(reads=("image", "request", "positive", "negative", "active_loras", "output", "cfg", "report",
                       "private"),
                writes=("files",))
def stage(t):
    """Writes the PNG with the metadata (none in private mode) and the report."""
    model = os.path.splitext(os.path.basename(t.cfg.checkpoint))[0]
    chunks = metadata.png_chunks(t.request, t.positive, t.negative, model, t.active_loras, private=t.private)
    folder = os.path.dirname(os.path.abspath(t.output))
    os.makedirs(folder, exist_ok=True)
    write_png(t.image, t.output, chunks)
    text = json.dumps(report(t, os.path.basename(t.output)), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json_path = report_path(t.output)
    _write_new(json_path, lambda f: f.write(text.encode("utf-8")))
    t.files = (t.output, json_path)
