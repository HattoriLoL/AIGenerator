"""The character sheets: one TOML file per character, with the tags that describe it, the negative, the LoRAs and
notes. The format is in docs/sheets.md.

Pure module (standard library only: tomllib reads, and writing is done here, only for the sheet fields).
"""
import json
import os
import re
import tomllib
import unicodedata

from aigen import contract

_text = (lambda v: isinstance(v, str))
SHEET_FIELDS = {
    "name": (lambda v: isinstance(v, str) and v.strip() != "", "a non-empty text", contract.REQUIRED),
    "tags": (_text, "a text (comma-separated tags)", ""),
    "negative": (_text, "a text (comma-separated tags)", ""),
    "notes": (_text, "a text", ""),
}


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
    sheet = contract.check_fields(info, SHEET_FIELDS, source)
    sheet["name"] = sheet["name"].strip()
    sheet["loras"] = contract.check_loras(loras, source)
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


def toml_text(sheet):
    """The TOML of a checked sheet (what write_sheet writes and read_sheet reads back the same)."""
    sheet = check_sheet(sheet)
    lines = ["sheet_version = %d" % contract.SHEET_VERSION]
    for field in SHEET_FIELDS:
        lines.append("%s = %s" % (field, _toml_string(sheet[field])))
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
