"""The character sheets: one TOML file per character, with the tags that describe it, the negative, the LoRAs, the
checkpoint it was made with, the generation settings that keep its look ([settings]) and notes. The format is in
docs/sheets.md.

Pure module (standard library only: tomllib reads, and writing is done here, only for the sheet fields).
"""
import json
import os
import re
import tomllib
import unicodedata

from aigen import contract

_text = (lambda v: isinstance(v, str))
CHECKPOINT_EXTENSIONS = (".safetensors", ".ckpt")
SHEET_FIELDS = {
    "name": (lambda v: isinstance(v, str) and v.strip() != "", "a non-empty text", contract.REQUIRED),
    "tags": (_text, "a text (comma-separated tags)", ""),
    "negative": (_text, "a text (comma-separated tags)", ""),
    "checkpoint": (lambda v: isinstance(v, str) and "/" not in v and "\\" not in v,
                   "the checkpoint's file name, without the folder (or \"\")", ""),
    "notes": (_text, "a text", ""),
}
# The request fields a sheet may set in [settings], in the order they are written; "hires" and "face_fix" (false, true
# or a table) come after them. The seed and the count change from one image to the next, so they are not here.
SETTINGS = ("quality", "style", "block_explicit", "width", "height", "steps", "cfg", "sampler")
PASSES = {"hires": contract.HIRES_FIELDS, "face_fix": contract.FACE_FIELDS}
NO_STYLE = "none"  # TOML has no null: style = "none" is the request's "style": null


def check_settings(info, where):
    """Checks a [settings] table and returns a copy with only the fields it gives (in SETTINGS order, then the
    passes): cfg as a float, style "none" as None, a pass as None (off) or with all its fields."""
    if not isinstance(info, dict):
        raise contract.RequestError("%s: 'settings' is not a TOML table" % where)
    for field in info:
        if field not in SETTINGS and field not in PASSES:
            raise contract.RequestError("%s: 'settings' has the unknown field '%s'; the fields are: %s"
                                        % (where, field, ", ".join(SETTINGS + tuple(PASSES))))
    result = {}
    for field in SETTINGS:
        if field not in info:
            continue
        value = None if field == "style" and info[field] == NO_STYLE else info[field]
        ok, expected, _ = contract.REQUEST_FIELDS[field]
        if field == "style":
            expected = " or ".join('"%s"' % s for s in contract.STYLES + (NO_STYLE,))
        if not ok(value):
            raise contract.RequestError("%s: 'settings' has '%s' = %s; expected %s"
                                        % (where, field, json.dumps(info[field], ensure_ascii=False), expected))
        result[field] = float(value) if field == "cfg" else value
    for field, fields in PASSES.items():
        if field in info:
            value = info[field]
            if value is not None and not isinstance(value, (bool, dict)):  # None: a checked sheet, checked again
                raise contract.RequestError("%s: 'settings' has '%s' = %s; expected true, false or a table"
                                            % (where, field, json.dumps(value, ensure_ascii=False)))
            result[field] = contract.optional(value, fields, field, where + ": 'settings'")
    return result


def settings_of(request):
    """The [settings] of a normalized request: all of its SETTINGS and passes."""
    return {field: request[field] for field in SETTINGS + tuple(PASSES)}


def apply_settings(request, sheet):
    """The request (not yet normalized) with the sheet's settings in the fields it does not give. The request wins:
    for a pass given as true or as an object in the request, the request's fields go over the sheet's."""
    result = dict(request)
    for field, value in sheet["settings"].items():
        if field not in result:
            result[field] = dict(value) if isinstance(value, dict) else value
        elif field in PASSES and isinstance(value, dict):
            given = result[field]
            if given is True:
                result[field] = dict(value)
            elif isinstance(given, dict):
                result[field] = dict(value, **given)
    return result


def fill_request(request, folder):
    """The request (not yet normalized) with the settings of its sheet (apply_settings), read from the sheets
    `folder`; a request without a sheet, or with a 'sheet' that is not a name, is returned as it is (normalize says
    what is wrong with it)."""
    name = request.get("sheet") if isinstance(request, dict) else None
    if not isinstance(name, str) or not name.strip():
        return request
    return apply_settings(request, read_sheet(resolve(name, folder)))


def model_name(name):
    """The checkpoint's name: the file name of a path, without .safetensors or .ckpt."""
    base = os.path.basename(name.strip())
    for extension in CHECKPOINT_EXTENSIONS:
        if base.lower().endswith(extension):
            return base[:-len(extension)]
    return base


def check_checkpoint(sheet, checkpoint):
    """A sheet with a 'checkpoint' only works with that checkpoint (the file name, with or without the extension, any
    case); raises RequestError when the configured `checkpoint` (a path) is another one."""
    if not sheet["checkpoint"].strip():
        return
    wanted, configured = model_name(sheet["checkpoint"]), model_name(checkpoint)
    if wanted.casefold() != configured.casefold():
        raise contract.RequestError("the sheet '%s' was made with the checkpoint '%s'; the configured one is '%s'"
                                    " (set [models] checkpoint in config.local.ini, or clear the sheet's checkpoint)"
                                    % (sheet["name"], wanted, configured))


def check_sheet(info, source="the sheet"):
    """Checks the sheet against version 1 and returns a full copy (with the defaults)."""
    if not isinstance(info, dict):
        raise contract.RequestError("%s is not a TOML table" % source)
    info = dict(info)
    version = info.pop("sheet_version", contract.SHEET_VERSION)
    if isinstance(version, bool) or not isinstance(version, int) or version != contract.SHEET_VERSION:
        raise contract.RequestError("%s has sheet_version %r; this version of AIGenerator only knows %d"
                                    % (source, version, contract.SHEET_VERSION))
    loras = info.pop("loras", [])
    settings = info.pop("settings", {})
    sheet = contract.check_fields(info, SHEET_FIELDS, source)
    sheet["name"] = sheet["name"].strip()
    sheet["checkpoint"] = sheet["checkpoint"].strip()
    sheet["loras"] = contract.check_loras(loras, source)
    sheet["settings"] = check_settings(settings, source)
    return dict(sheet, sheet_version=contract.SHEET_VERSION)


def read_sheet(path):
    """Reads and checks a sheet. Raises RequestError if it cannot."""
    if not os.path.isfile(path):
        raise contract.RequestError("sheet not found: " + path)
    try:
        with open(path, "rb") as f:
            info = tomllib.load(f)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise contract.RequestError("the sheet %s is not valid TOML: %s" % (os.path.basename(path), e))
    return check_sheet(info, "the sheet " + os.path.basename(path))


def resolve(value, folder):
    """The file of a sheet: a path (ends in .toml or has a slash) is taken as it is; a name is looked up in the sheets
    folder (`folder`/<name>.toml)."""
    if value.endswith(".toml") or "/" in value or os.sep in value:
        return os.path.abspath(os.path.expanduser(value))
    return os.path.join(folder, value + ".toml")


def list_sheets(folder):
    """The names (without .toml) of the sheets in the folder, sorted; [] if the folder does not exist."""
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.splitext(n)[0] for n in os.listdir(folder) if n.endswith(".toml"))


def file_name(name):
    """The file name of a sheet from the character's name: lower case, no accents, only [a-z0-9_-]."""
    no_accents = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^a-z0-9_-]+", "_", no_accents.lower()).strip("_")
    if not clean:
        raise contract.RequestError("the name %r does not make a file name (use letters or digits)" % name)
    return clean


def _toml_string(v):
    # a JSON string is a valid TOML basic string (the same quotes and the same escapes)
    return json.dumps(v, ensure_ascii=False)


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return _toml_string(v) if isinstance(v, str) else str(v)


def settings_lines(settings, prefix=""):
    """The TOML lines of checked settings: the fields, then each pass that is on as a [<prefix>hires] table."""
    lines = []
    for field in SETTINGS:
        if field in settings:
            value = NO_STYLE if field == "style" and settings[field] is None else settings[field]
            lines.append("%s = %s" % (field, _toml_value(value)))
    for field in PASSES:
        if field in settings and settings[field] is None:
            lines.append("%s = false" % field)
    for field in PASSES:
        if settings.get(field):
            lines += ["", "[%s%s]" % (prefix, field)]
            lines += ["%s = %s" % (k, _toml_value(v)) for k, v in settings[field].items()]
    return lines


def settings_text(settings):
    """The settings as the TOML text the web interface shows (passes as [hires] and [face_fix])."""
    return "\n".join(settings_lines(settings)).strip() + ("\n" if settings else "")


def parse_settings(text, where="the settings"):
    """The checked settings of a TOML text (the reverse of settings_text); an empty text gives no settings."""
    try:
        info = tomllib.loads(text or "")
    except tomllib.TOMLDecodeError as e:
        raise contract.RequestError("%s are not valid TOML: %s" % (where, e))
    return check_settings(info, where)


def toml_text(sheet):
    """The TOML of a checked sheet (what write_sheet writes and read_sheet reads back the same)."""
    sheet = check_sheet(sheet)
    lines = ["sheet_version = %d" % contract.SHEET_VERSION]
    for field in SHEET_FIELDS:
        lines.append("%s = %s" % (field, _toml_string(sheet[field])))
    if sheet["settings"]:
        lines += ["", "[settings]"] + settings_lines(sheet["settings"], "settings.")
    for lora in sheet["loras"]:
        lines += ["", "[[loras]]", "name = %s" % _toml_string(lora["name"]), "weight = %r" % float(lora["weight"])]
    return "\n".join(lines) + "\n"


def write_sheet(sheet, path, overwrite=False):
    """Writes the sheet to `path`; without `overwrite`, a sheet that already exists is refused."""
    text = toml_text(sheet)
    if os.path.exists(path) and not overwrite:
        raise contract.RequestError("the sheet already exists: " + path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path
