"""The AIGenerator input and output contract: the format versions, the exit codes and the check of the generation
request. The full description, for whoever calls the program, is in docs/contract.md.

Pure module (standard library only): the tests use it directly (tests/test_contract.py).
"""
import json
import math
import os

# Format versions. A new version only when a field changes meaning or is removed; a new optional field does not.
REQUEST_VERSION = 1  # the generation request (JSON), field "request_version"; without the field, it is 1
SHEET_VERSION = 1    # the character sheet (TOML), field "sheet_version"; without the field, it is 1
FORMAT_VERSION = 1   # the .aigen.json report, the batch.aigen.json summary and the PNG "aigen" chunk, "format_version"

# Exit codes (the same in generate.py and batch.py).
OK = 0
GENERATION_FAILED = 1  # an image could not be made (the model did not load, a stage failed; in batch mode, a request)
BAD_REQUEST = 2        # the request is wrong, nothing was loaded or written (option, field, sheet, LoRA, model, output)

# The samplers and the name AUTOMATIC1111 gives each one (what goes in the PNG "parameters" text). The diffusers class
# of each one is in model.py.
SAMPLERS = {
    "euler_a": "Euler a",
    "euler": "Euler",
    "dpmpp_2m": "DPM++ 2M",
    "dpmpp_2m_karras": "DPM++ 2M Karras",
    "dpmpp_2m_sde_karras": "DPM++ 2M SDE Karras",
    "ddim": "DDIM",
}
UPSCALERS = ("model", "lanczos")
STYLES = ("anime",)                 # the tags of each style are in prompts.py

SIDE_MIN, SIDE_MAX = 256, 2048      # width and height of the first pass, multiples of 8
SIDE_MAX_HIRES = 4096               # width and height after the hires fix
SEED_MAX = 2 ** 32 - 1
LORA_WEIGHT_MAX = 4.0               # a LoRA weight is between -4 and 4


REQUIRED = object()                 # the "default" of a field that may not be missing


class RequestError(Exception):
    """The request cannot start: it ends with BAD_REQUEST, before the model is loaded and before anything is written."""


ROOT_SCRIPTS = ("setup",)          # in the repository root on Linux too; the other .sh launchers are in bin/


def command(name, windows=None):
    """How the user calls the program on this system, for the usage and error messages: name.bat on Windows (all the
    .bat launchers are in the root), bin/name.sh (or ./setup.sh) elsewhere."""
    if os.name == "nt" if windows is None else windows:
        return name + ".bat"
    return ("./%s.sh" if name in ROOT_SCRIPTS else "bin/%s.sh") % name


def _number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:  # a JSON integer too large for a float
        return False


def _integer(minimum, maximum):
    def ok(v):
        return isinstance(v, int) and not isinstance(v, bool) and minimum <= v <= maximum
    return ok


def _range(minimum, maximum, open_min=False):
    def ok(v):
        if not _number(v):
            return False
        return (v > minimum if open_min else v >= minimum) and v <= maximum
    return ok


def _side(v):
    return _integer(SIDE_MIN, SIDE_MAX)(v) and v % 8 == 0


def _text(v):
    return isinstance(v, str)


def _seed(v):
    return isinstance(v, int) and not isinstance(v, bool) and (v == -1 or 0 <= v <= SEED_MAX)


def _sheet(v):
    return v is None or (isinstance(v, str) and v.strip() != "")


# The request fields, in version 1: (check, what is expected, default or REQUIRED). "loras", "hires" and "face_fix"
# have their own check (below).
REQUEST_FIELDS = {
    "prompt": (_text, "a text (comma-separated tags)", ""),
    "negative": (_text, "a text", ""),
    "sheet": (_sheet, "the name of a sheet, the path of a .toml or null", None),
    "quality": (lambda v: isinstance(v, bool), "true or false", True),
    "style": (lambda v: v is None or v in STYLES, " or ".join('"%s"' % s for s in STYLES) + " or null", "anime"),
    "block_explicit": (lambda v: isinstance(v, bool), "true or false", True),
    "width": (_side, "a multiple of 8 from %d to %d" % (SIDE_MIN, SIDE_MAX), 1024),
    "height": (_side, "a multiple of 8 from %d to %d" % (SIDE_MIN, SIDE_MAX), 1024),
    "steps": (_integer(1, 150), "an integer from 1 to 150", 25),
    "cfg": (_range(1.0, 30.0), "a number from 1 to 30", 7.0),
    "sampler": (lambda v: v in SAMPLERS, "one of: " + ", ".join(SAMPLERS), "euler_a"),
    "seed": (_seed, "-1 (drawn) or an integer from 0 to %d" % SEED_MAX, -1),
    "count": (_integer(1, 64), "an integer from 1 to 64", 1),
}
HIRES_FIELDS = {
    "scale": (_range(1.0, 4.0, open_min=True), "a number greater than 1 and up to 4", 1.5),
    "strength": (_range(0.0, 1.0, open_min=True), "a number greater than 0 and up to 1", 0.4),
    "steps": (_integer(1, 150), "an integer from 1 to 150", 15),
    "upscaler": (lambda v: v in UPSCALERS, "\"model\" or \"lanczos\"", "model"),
}
FACE_FIELDS = {
    "strength": (_range(0.0, 1.0, open_min=True), "a number greater than 0 and up to 1", 0.4),
    "steps": (_integer(1, 150), "an integer from 1 to 150", 20),
    "margin": (_range(0.0, 2.0), "a number from 0 to 2", 0.3),
    "prompt": (_text, "a text (extra tags for the face)", ""),
    "max_faces": (_integer(1, 16), "an integer from 1 to 16", 4),
}
LORA_FIELDS = {
    "name": (lambda v: isinstance(v, str) and v.strip() != "", "the name of a file in the LoRA folder", REQUIRED),
    "weight": (_range(-LORA_WEIGHT_MAX, LORA_WEIGHT_MAX), "a number from -%g to %g" % (LORA_WEIGHT_MAX, LORA_WEIGHT_MAX),
               1.0),
}


def _value(v):
    return json.dumps(v, ensure_ascii=False)


def check_fields(info, fields, where):
    """Checks an object against a field table and returns a copy with the defaults of the missing fields. A field the
    table does not know is refused (it is almost always a typo)."""
    if not isinstance(info, dict):
        raise RequestError("%s is not a JSON object" % where)
    for field in info:
        if field not in fields:
            raise RequestError("%s has the unknown field '%s'; the fields are: %s"
                               % (where, field, ", ".join(fields)))
    result = {}
    for field, (ok, expected, default) in fields.items():
        if field not in info:
            if default is REQUIRED:
                raise RequestError("%s does not have the required field '%s' (%s)" % (where, field, expected))
            result[field] = default
            continue
        if not ok(info[field]):
            raise RequestError("%s has '%s' = %s; expected %s" % (where, field, _value(info[field]), expected))
        result[field] = info[field]
    return result


def check_loras(loras, where):
    """A list of {"name", "weight"}; returns the list with the default weight (1) where it is missing."""
    if not isinstance(loras, list):
        raise RequestError("%s has 'loras' = %s; expected a list of {\"name\", \"weight\"}" % (where, _value(loras)))
    result = []
    for i, lora in enumerate(loras, 1):
        item = check_fields(lora, LORA_FIELDS, "%s: LoRA %d" % (where, i))
        item["name"] = item["name"].strip()
        item["weight"] = float(item["weight"])
        result.append(item)
    return result


def _optional(value, fields, name, where):
    """hires and face_fix: absent, null or false is off; true is on with the defaults; an object is on."""
    if value is None or value is False:
        return None
    if value is True:
        value = {}
    return check_fields(value, fields, "%s: '%s'" % (where, name))


def normalize(info, source="the request"):
    """Checks the request against version 1 and returns a full copy (with the defaults). Does not change the given
    dictionary. Raises RequestError saying which field and what is expected."""
    if not isinstance(info, dict):
        raise RequestError("%s is not a JSON object" % source)
    info = dict(info)
    version = info.pop("request_version", REQUEST_VERSION)
    if isinstance(version, bool) or not isinstance(version, (int, float)) or version != REQUEST_VERSION:
        raise RequestError("%s has request_version %s; this version of AIGenerator only knows %d"
                           % (source, _value(version), REQUEST_VERSION))
    loras = info.pop("loras", [])
    hires = info.pop("hires", None)
    face_fix = info.pop("face_fix", None)
    request = check_fields(info, REQUEST_FIELDS, source)
    request["cfg"] = float(request["cfg"])
    request["loras"] = check_loras(loras, source)
    request["hires"] = _optional(hires, HIRES_FIELDS, "hires", source)
    request["face_fix"] = _optional(face_fix, FACE_FIELDS, "face_fix", source)
    if not request["prompt"].strip() and request["sheet"] is None:
        raise RequestError("%s has nothing to generate: 'prompt' is empty and there is no 'sheet'" % source)
    if request["hires"]:
        side = max(request["width"], request["height"]) * request["hires"]["scale"]
        if side > SIDE_MAX_HIRES:
            raise RequestError("%s: with the hires fix, the larger side would reach %d px; the maximum is %d"
                               % (source, round(side), SIDE_MAX_HIRES))
    return dict(request, request_version=REQUEST_VERSION)


def read_request(path):
    """Reads a request from a JSON file, without checking it (the caller merges the options and calls normalize)."""
    if not os.path.isfile(path):
        raise RequestError("request not found: " + path)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise RequestError("the request %s is not valid JSON: %s" % (os.path.basename(path), e))


def hires_side(side, scale):
    """The side after the hires fix: side × scale, rounded to the nearest multiple of 8."""
    return max(8, int(round(side * scale / 8.0)) * 8)
