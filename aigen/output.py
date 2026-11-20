"""The writing: the PNG (with the "parameters" and "aigen" chunks) and the .aigen.json report next to it. No file
that already exists is overwritten.
"""
import json
import os
import time

from aigen import VERSION, contract, metadata, stages

REPORT_SUFFIX = ".aigen.json"


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


def report(t, png_name):
    """The dictionary of the .aigen.json report."""
    return {"format_version": contract.FORMAT_VERSION, "aigen": VERSION, "png": png_name, "request": t.request,
            "model": os.path.basename(t.cfg.checkpoint), "seconds": round(time.time() - t.t_start, 2),
            "timings": dict(t.timings), **t.report}


def _write_new(path, write):
    """Creates the file only if it does not exist (mode "x"): two generations at the same time never write over each
    other."""
    with open(path, "xb") as f:
        write(f)


@stages.declare(reads=("image", "request", "positive", "negative", "active_loras", "output", "cfg", "report"),
                writes=("files",))
def stage(t):
    """Writes the PNG with the metadata and the report."""
    from PIL.PngImagePlugin import PngInfo
    model = os.path.splitext(os.path.basename(t.cfg.checkpoint))[0]
    info = PngInfo()
    info.add_text(metadata.A1111_KEY, metadata.parameters_text(t.request, t.positive, t.negative, model,
                                                               t.active_loras))
    info.add_text(metadata.AIGEN_KEY, metadata.aigen_chunk(t.request, t.positive, t.negative, t.active_loras))
    folder = os.path.dirname(os.path.abspath(t.output))
    os.makedirs(folder, exist_ok=True)
    _write_new(t.output, lambda f: t.image.save(f, format="PNG", pnginfo=info))
    text = json.dumps(report(t, os.path.basename(t.output)), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json_path = report_path(t.output)
    _write_new(json_path, lambda f: f.write(text.encode("utf-8")))
    t.files = (t.output, json_path)
