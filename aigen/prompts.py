"""The prompt assembly: the Pony quality tags, the character sheet and the scene, without repeated tags; and the
translation of the AUTOMATIC1111 weights ("(tag:1.2)", "(tag)", "[tag]") to the compel syntax ("(tag)1.2").

Pure module (standard library only), except the stage, which only touches the job.
"""
import re

from aigen import stages

# The Pony Diffusion V6 XL quality tags (the model was trained with them; without them the quality drops), put in front
# of the prompt when the request has "quality": true. The negative gets the low scores.
QUALITY_TAGS = "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up"
QUALITY_TAGS_NEGATIVE = "score_6, score_5, score_4"
# The styles ("style" in the request): the Pony source tags, (positive, negative). The names are those of
# contract.STYLES.
STYLES = {
    "anime": ("source_anime", "source_cartoon, source_furry, source_pony, 3d, realistic, photorealistic"),
}
# "block_explicit": true asks for content without an explicit rating, (positive, negative).
SAFE_TAGS = ("rating_safe", "rating_questionable, rating_explicit")


def split_tags(text):
    """The tags of a text, split at the commas that are outside parentheses and brackets ("\\(" does not count)."""
    tags, current, level, i = [], [], 0, 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            current.append(text[i:i + 2])
            i += 2
            continue
        if c in "([":
            level += 1
        elif c in ")]" and level > 0:
            level -= 1
        if c == "," and level == 0:
            tags.append("".join(current))
            current = []
        else:
            current.append(c)
        i += 1
    tags.append("".join(current))
    return [t.strip() for t in tags if t.strip()]


def _key(tag):
    return re.sub(r"\s+", " ", tag.strip().lower())


def join_tags(*parts):
    """Joins the texts into a single tag list, in order, without repeats (the first occurrence wins; case and extra
    spaces do not count)."""
    seen, result = set(), []
    for part in parts:
        for tag in split_tags(part or ""):
            if _key(tag) not in seen:
                seen.add(_key(tag))
                result.append(tag)
    return ", ".join(result)


def build(request, sheet=None):
    """(positive, negative) of a normalized request and a sheet (or None), in this order: quality, style, rating,
    sheet and scene."""
    quality = (QUALITY_TAGS, QUALITY_TAGS_NEGATIVE) if request["quality"] else ("", "")
    style = STYLES[request["style"]] if request["style"] else ("", "")
    safe = SAFE_TAGS if request["block_explicit"] else ("", "")
    from_sheet = (sheet["tags"], sheet["negative"]) if sheet else ("", "")
    scene = (request["prompt"], request["negative"])
    parts = (quality, style, safe, from_sheet, scene)
    return join_tags(*(p[0] for p in parts)), join_tags(*(p[1] for p in parts))


def merge_loras(from_sheet, from_request):
    """The sheet's LoRAs and the request's, without repeating a name: the request's weight wins over the sheet's."""
    weights = {}
    for lora in list(from_sheet) + list(from_request):
        weights[lora["name"]] = lora["weight"]
    return [{"name": n, "weight": w} for n, w in weights.items()]


# The pieces of the AUTOMATIC1111 syntax (the same design as its parse_prompt_attention).
_ATTENTION = re.compile(r"\\\(|\\\)|\\\[|\\\]|\\\\|\\|\(|\[|:\s*([+-]?[.\d]+)\s*\)|\)|\]|[^\\()\[\]:]+|:")
_UP, _DOWN = 1.1, 1 / 1.1


def _weight(text):
    try:
        return float(text)
    except ValueError:
        return None


def weights(text):
    """[(chunk, weight)] of a prompt in the AUTOMATIC1111 syntax: "(x:1.3)" multiplies by 1.3, "(x)" by 1.1 and
    "[x]" divides by 1.1; nested, they multiply; "\\(" is a literal parenthesis. Neighboring chunks with the same
    weight become one."""
    res, open_parens, open_brackets = [], [], []

    def multiply(start, factor):
        for p in range(start, len(res)):
            res[p][1] *= factor

    for m in _ATTENTION.finditer(text):
        piece, number = m.group(0), m.group(1)
        weight = _weight(number) if number is not None else None
        if piece.startswith("\\"):
            res.append([piece[1:] if len(piece) > 1 else piece, 1.0])
        elif piece == "(":
            open_parens.append(len(res))
        elif piece == "[":
            open_brackets.append(len(res))
        elif weight is not None and open_parens:
            multiply(open_parens.pop(), weight)
        elif piece == ")" and open_parens:
            multiply(open_parens.pop(), _UP)
        elif piece == "]" and open_brackets:
            multiply(open_brackets.pop(), _DOWN)
        else:
            res.append([piece, 1.0])
    for start in open_parens:
        multiply(start, _UP)
    for start in open_brackets:
        multiply(start, _DOWN)
    merged = []
    for chunk, weight in res:
        if merged and abs(merged[-1][1] - weight) < 1e-9:
            merged[-1][0] += chunk
        else:
            merged.append([chunk, weight])
    return [(c, w) for c, w in merged if c]


def _escape_compel(chunk):
    return re.sub(r"([()\\])", r"\\\1", chunk)


def to_compel(text):
    """The prompt in the compel syntax: each chunk with a weight other than 1 becomes "(chunk)weight"."""
    parts = []
    for chunk, weight in weights(text):
        escaped = _escape_compel(chunk)
        if abs(weight - 1.0) < 1e-6:
            parts.append(escaped)
        elif escaped.strip(" ,"):
            before = escaped[:len(escaped) - len(escaped.lstrip(" ,"))]
            after = escaped[len(escaped.rstrip(" ,")):]
            parts.append("%s(%s)%s%s" % (before, escaped.strip(" ,"), ("%.4f" % weight).rstrip("0").rstrip("."), after))
        else:
            parts.append(escaped)
    return "".join(parts)


@stages.declare(reads=("request", "sheet", "report"), writes=("positive", "negative", "loras"))
def stage(t):
    """Builds the final prompt and the LoRA list (the sheet's and the request's)."""
    t.positive, t.negative = build(t.request, t.sheet)
    t.loras = merge_loras(t.sheet["loras"] if t.sheet else [], t.request["loras"])
    t.report["prompt"] = {"positive": t.positive, "negative": t.negative}
