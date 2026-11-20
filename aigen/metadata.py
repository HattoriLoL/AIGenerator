"""What goes inside the PNG: the "parameters" text in the AUTOMATIC1111 format (which other programs and sites read)
and the "aigen" chunk, a JSON with the full request, from which the image can be made again. In private mode (the
prompts not saved) the PNG gets no text chunk at all, and the request in the report loses what tells what the image
is (redact_request).

Pure module (standard library only): the PNG chunks are written by output.py and read by web.py.
"""
import json

from aigen import VERSION, contract

A1111_KEY = "parameters"
AIGEN_KEY = "aigen"

# In private mode: the request fields that tell what the image is, and the face fix field that does too.
PRIVATE_REQUEST_FIELDS = ("prompt", "negative", "sheet", "loras")
PRIVATE_FACE_FIELDS = ("prompt",)


def parameters_text(request, positive, negative, model, loras=()):
    """The "parameters" text: the prompt, the negative and a "Field: value, ..." line. The LoRAs go in the prompt as
    <lora:name:weight>, as AUTOMATIC1111 writes them."""
    prompt_line = positive + "".join(" <lora:%s:%g>" % (l["name"], l["weight"]) for l in loras)
    fields = [("Steps", request["steps"]), ("Sampler", contract.SAMPLERS[request["sampler"]]),
              ("CFG scale", "%g" % request["cfg"]), ("Seed", request["seed"]),
              ("Size", "%dx%d" % (request["width"], request["height"]))]
    if model:
        fields.append(("Model", model))
    h = request["hires"]
    if h:
        fields += [("Denoising strength", "%g" % h["strength"]), ("Hires upscale", "%g" % h["scale"]),
                   ("Hires steps", h["steps"]), ("Hires upscaler", h["upscaler"])]
    if request["face_fix"]:
        fields.append(("Face fix strength", "%g" % request["face_fix"]["strength"]))
    fields.append(("Version", "aigen " + VERSION))
    lines = [prompt_line]
    if negative:
        lines.append("Negative prompt: " + negative)
    lines.append(", ".join("%s: %s" % (k, v) for k, v in fields))
    return "\n".join(lines)


def aigen_chunk(request, positive, negative, loras=()):
    """The JSON of the "aigen" chunk: the request (with the seed used), the final prompt and the LoRAs."""
    return json.dumps({"format_version": contract.FORMAT_VERSION, "request": request, "positive": positive,
                       "negative": negative, "loras": list(loras)}, ensure_ascii=False, sort_keys=True)


def png_chunks(request, positive, negative, model, loras=(), private=False):
    """The text chunks of the PNG ({key: text}): "parameters" and "aigen"; none in private mode."""
    if private:
        return {}
    return {A1111_KEY: parameters_text(request, positive, negative, model, loras),
            AIGEN_KEY: aigen_chunk(request, positive, negative, loras)}


def redact_request(request):
    """A copy of the request without what tells what the image is: the prompt, the negative, the sheet, the LoRAs and
    the face fix prompt. The numbers (seed, sizes, steps, ...) stay. Does not change the given request."""
    kept = {k: v for k, v in request.items() if k not in PRIVATE_REQUEST_FIELDS}
    if isinstance(kept.get("face_fix"), dict):
        kept["face_fix"] = {k: v for k, v in kept["face_fix"].items() if k not in PRIVATE_FACE_FIELDS}
    return kept


def request_from_png(texts):
    """The (normalized) request kept in the text chunks of a PNG ({key: text}). Raises RequestError if the PNG was
    not made by AIGenerator."""
    if AIGEN_KEY not in texts:
        raise contract.RequestError("the PNG has no AIGenerator data (no '%s' chunk): it was made in private mode, with"
                                    " the prompts not saved, or by another program" % AIGEN_KEY)
    try:
        info = json.loads(texts[AIGEN_KEY])
    except ValueError as e:
        raise contract.RequestError("the PNG '%s' chunk is not valid JSON: %s" % (AIGEN_KEY, e))
    if not isinstance(info, dict) or info.get("format_version") != contract.FORMAT_VERSION:
        raise contract.RequestError("the PNG '%s' chunk has a format_version this version does not know" % AIGEN_KEY)
    return contract.normalize(info.get("request"), "the request in the PNG")
