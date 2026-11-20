"""The program: the options, the job and the stage sequence of a generation.

    bin/aigen.sh output.png [--request request.json] [--prompt "..."] [--sheet name] [options]

The command-line options override the fields of --request; --private and --save-prompts override the config's
[privacy] save_prompts for the run. All of them are in docs/options.md; the request, in docs/contract.md. Exit code:
0 ok, 1 the image was not made, 2 the request is wrong and nothing was done.
"""
import argparse
import os
import random
import sys
import time

from aigen import (VERSION, config, contract, face, generation, hires, loras, memory, model, output, prompts,
                   sheets, stages)


class _Options(argparse.ArgumentParser):
    """An option error ends with BAD_REQUEST and the message starts with ERROR:, like every AIGenerator error."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print("ERROR: " + message, file=sys.stderr)
        sys.exit(contract.BAD_REQUEST)


def _generation_options(p):
    g = p.add_argument_group("generation")
    g.add_argument("--request", help="a request in JSON (docs/contract.md); the options below override it")
    g.add_argument("--prompt", help="the scene tags, comma-separated")
    g.add_argument("--negative", help="the negative tags")
    g.add_argument("--sheet", help="a character sheet: the name (in the sheets folder) or the path of a .toml")
    g.add_argument("--no-quality", action="store_true", help="do not put the Pony score_* tags in the prompt")
    g.add_argument("--style", choices=list(contract.STYLES) + ["none"],
                   help="the Pony source tags (default: anime); none adds no source tag")
    g.add_argument("--allow-explicit", action="store_true",
                   help="do not add the tags that block the explicit rating (rating_safe in the positive, ...)")
    g.add_argument("--width", type=int)
    g.add_argument("--height", type=int)
    g.add_argument("--steps", type=int)
    g.add_argument("--cfg", type=float)
    g.add_argument("--sampler", choices=list(contract.SAMPLERS))
    g.add_argument("--seed", type=int, help="-1 draws one (the default)")
    g.add_argument("--count", type=int, help="how many images (consecutive seeds); written as x_001.png, x_002.png ...")
    g.add_argument("--lora", action="append", metavar="NAME[:WEIGHT]",
                   help="a LoRA from the LoRA folder (repeat for more than one); added to the request's and sheet's")


def _extra_options(p):
    h = p.add_argument_group("hires fix (off by default)")
    h.add_argument("--hires", action="store_true", help="turn on the hires fix")
    h.add_argument("--hires-scale", type=float)
    h.add_argument("--hires-strength", type=float)
    h.add_argument("--hires-steps", type=int)
    h.add_argument("--hires-upscaler", choices=list(contract.UPSCALERS))
    f = p.add_argument_group("face fix (off by default)")
    f.add_argument("--face-fix", action="store_true", help="turn on the face fix")
    f.add_argument("--face-fix-strength", type=float)
    f.add_argument("--face-fix-steps", type=int)
    f.add_argument("--face-fix-margin", type=float)
    f.add_argument("--face-fix-prompt", help="extra tags for the face only")
    f.add_argument("--face-fix-max", type=int, help="how many faces at most")


def privacy_options(p):
    """--private and --save-prompts (giving both is an option error: exit 2); without them, the config decides."""
    g = p.add_argument_group("privacy (default: [privacy] save_prompts in the config, true)")
    m = g.add_mutually_exclusive_group()
    m.add_argument("--private", action="store_true",
                   help="do not save the prompts: the PNG gets no text chunk and the report leaves out the prompts,"
                        " the sheet and the LoRAs")
    m.add_argument("--save-prompts", action="store_true", help="save the prompts in the PNG and the report")


def private_mode(a, cfg):
    """Whether the run is private: --private or --save-prompts if given, else the config (not save_prompts)."""
    if a.private:
        return True
    if a.save_prompts:
        return False
    return not cfg.save_prompts


def parse_args(argv, prog=None):
    p = _Options(prog=prog or contract.command("aigen"),
                 description="Generates anime character images with Pony Diffusion XL.")
    p.add_argument("output", help="the PNG to write (never overwritten); the report goes next to it, as .aigen.json")
    p.add_argument("--version", action="version", version="AIGenerator " + VERSION)
    _generation_options(p)
    _extra_options(p)
    privacy_options(p)
    return p.parse_args(argv)


SIMPLE = {"prompt": "prompt", "negative": "negative", "sheet": "sheet", "width": "width", "height": "height",
          "steps": "steps", "cfg": "cfg", "sampler": "sampler", "seed": "seed", "count": "count"}
HIRES = {"scale": "hires_scale", "strength": "hires_strength", "steps": "hires_steps", "upscaler": "hires_upscaler"}
FACE_FIX = {"strength": "face_fix_strength", "steps": "face_fix_steps", "margin": "face_fix_margin",
            "prompt": "face_fix_prompt", "max_faces": "face_fix_max"}


def _merge_optional(base, field, turn_on, values):
    current = base.get(field)
    if turn_on or values:
        base[field] = dict(current if isinstance(current, dict) else {}, **values)


def request_from_args(a):
    """The normalized request: the one of --request (or an empty one), with the given options on top."""
    base = contract.read_request(a.request) if a.request else {}
    if not isinstance(base, dict):
        raise contract.RequestError("the request %s is not a JSON object" % a.request)
    base = dict(base)
    for field, option in SIMPLE.items():
        if getattr(a, option) is not None:
            base[field] = getattr(a, option)
    if a.no_quality:
        base["quality"] = False
    if a.style:
        base["style"] = None if a.style == "none" else a.style
    if a.allow_explicit:
        base["block_explicit"] = False
    if a.lora:
        extra = loras.parse_list(",".join(a.lora))
        base["loras"] = list(base.get("loras") or []) + extra
    _merge_optional(base, "hires", a.hires, {k: getattr(a, o) for k, o in HIRES.items() if getattr(a, o) is not None})
    _merge_optional(base, "face_fix", a.face_fix,
                    {k: getattr(a, o) for k, o in FACE_FIX.items() if getattr(a, o) is not None})
    return contract.normalize(base, "the request" if not a.request else "the request " + os.path.basename(a.request))


class Job:
    """What the stages read and write in a generation (one image). At the start, only stages.BASE."""

    def __init__(self, request, output_png, session, cfg, private=False):
        self.request, self.output, self.session, self.cfg = request, output_png, session, cfg
        self.private = bool(private)  # the prompts are not saved (output.stage)
        self.t_start, self.timings, self.memory = time.time(), {}, {}


@stages.declare(reads=("request", "cfg", "output"), writes=("sheet", "report"))
def check_request(t):
    """Everything that can be checked without loading the model: the libraries, the model files, the sheet, the LoRAs
    and the output. A problem here is a RequestError: nothing was loaded or written."""
    r, cfg = t.request, t.cfg
    needed = model.LIBRARIES + (model.HIRES_LIBRARIES if r["hires"] else ()) + \
        (model.FACE_LIBRARIES if r["face_fix"] else ())
    model.check_libraries(needed)
    if not cfg.checkpoint or not os.path.isfile(cfg.checkpoint):
        raise contract.RequestError("checkpoint not found (%s): set [models] checkpoint in config.local.ini"
                                    " or the AIGEN_CHECKPOINT variable" % (cfg.checkpoint or "none configured"))
    if r["hires"] and r["hires"]["upscaler"] == "model" and not os.path.isfile(cfg.upscaler):
        raise contract.RequestError("upscaler model not found: %s (or use --hires-upscaler lanczos)" % cfg.upscaler)
    if r["face_fix"] and not os.path.isfile(cfg.face_detector):
        raise contract.RequestError("face detector not found: " + cfg.face_detector)
    t.sheet = sheets.read_sheet(sheets.resolve(r["sheet"], cfg.sheets_folder)) if r["sheet"] else None
    for lora in (t.sheet["loras"] if t.sheet else []) + r["loras"]:
        if not loras.find_file(cfg.loras_folder, lora["name"]):
            raise contract.RequestError("LoRA not found: '%s' (in the folder %s)" % (lora["name"], cfg.loras_folder))
    output.check_outputs([t.output])
    t.report = {"sheet": t.sheet["name"] if t.sheet else None}


def sequence(request):
    """The stages of a request: the hires fix and the face fix only when requested."""
    s = [check_request, prompts.stage, model.stage, loras.stage, generation.stage]
    if request["hires"]:
        s.append(hires.stage)
    if request["face_fix"]:
        s.append(face.stage)
    s.append(output.stage)
    return tuple(s)


def run(request, output_png, session, cfg, notify=None, private=None):
    """Generates the images of a normalized request and returns [(png, report)]. The outputs are all checked before
    the first one; with seed -1, one is drawn and the following ones add 1. `private` (the prompts not saved) is,
    when None, the config's: not cfg.save_prompts. After each image (made or failed), the memory that is no longer
    used is given back (memory.free); the model stays loaded in the session."""
    private = not cfg.save_prompts if private is None else bool(private)
    pngs = output.paths(output_png, request["count"])
    output.check_outputs(pngs)
    first_seed = request["seed"] if request["seed"] >= 0 else random.randrange(contract.SEED_MAX + 1)
    done = []
    for i, png in enumerate(pngs):
        one = dict(request, seed=(first_seed + i) % (contract.SEED_MAX + 1), count=1)
        seq = sequence(one)
        stages.check(seq)
        t = Job(one, png, session, cfg, private)
        try:
            for f in seq:
                start = time.time()
                memory.start()
                f(t)
                t.timings[stages.name(f)] = round(time.time() - start, 3)
                t.memory[stages.name(f)] = memory.measure()
        finally:
            memory.free()
        done.append(t.files)
        if notify:
            notify("%s (seed %d, %.1f s)" % (png, one["seed"], time.time() - t.t_start))
    return done


def main(argv=None):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        cfg = config.read()
        request = request_from_args(a)
        run(request, os.path.abspath(a.output), model.Session(cfg), cfg, notify=print, private=private_mode(a, cfg))
    except contract.RequestError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return contract.BAD_REQUEST
    except Exception as e:  # the model did not load, the GPU ran out of memory, ...
        print("ERROR: the generation failed: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return contract.GENERATION_FAILED
    return contract.OK


if __name__ == "__main__":
    sys.exit(main())
