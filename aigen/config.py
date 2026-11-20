"""The configuration: where the model, the LoRAs, the upscaler and the face detector are, the sheets and output
folders, the web port, when the web interface lets go of the model ([web] unload_after) and whether the prompts are
saved in the outputs ([privacy] save_prompts).

The order, from what weighs most to what weighs least: the environment variable (AIGEN_CHECKPOINT, ...),
config.local.ini (outside git: a machine's paths) and config.ini (versioned, only the template). A relative path is
relative to the repository root; "~" is the user's home folder.

Pure module (standard library only).
"""
import configparser
import os

from aigen import contract

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# attribute: (section, key, environment variable, default, is a path)
KEYS = {
    "checkpoint": ("models", "checkpoint", "AIGEN_CHECKPOINT", "", True),
    "vae": ("models", "vae", "AIGEN_VAE", "", True),
    "loras_folder": ("models", "loras_folder", "AIGEN_LORAS", "models/loras", True),
    "upscaler": ("models", "upscaler", "AIGEN_UPSCALER", "models/upscalers/RealESRGAN_x4plus_anime_6B.pth", True),
    "face_detector": ("models", "face_detector", "AIGEN_FACE_DETECTOR",
                      "models/detectors/lbpcascade_animeface.xml", True),
    "sheets_folder": ("folders", "sheets", "AIGEN_SHEETS", "characters", True),
    "output_folder": ("folders", "output", "AIGEN_OUTPUT", "output", True),
    "port": ("web", "port", "AIGEN_PORT", "7860", False),
    "unload_after": ("web", "unload_after", "AIGEN_UNLOAD_AFTER", "10", False),
    "save_prompts": ("privacy", "save_prompts", "AIGEN_SAVE_PROMPTS", "true", False),
}
TRUE = ("true", "yes", "1", "on")
FALSE = ("false", "no", "0", "off")


class Config:
    """The resolved values (absolute paths, or "" when not configured)."""

    def __init__(self, values):
        for name, value in values.items():
            setattr(self, name, value)

    def __repr__(self):
        return "Config(%s)" % ", ".join("%s=%r" % (n, getattr(self, n)) for n in KEYS)


def _path(value, root):
    value = os.path.expanduser(value.strip())
    if not value:
        return ""
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(root, value))


def _port(text):
    try:
        port = int(text)
    except ValueError:
        port = -1
    if not 1 <= port <= 65535:
        raise contract.RequestError("the web interface port is %r; expected an integer from 1 to 65535" % text)
    return port


def _minutes(text):
    try:
        minutes = int(text)
    except ValueError:
        minutes = -1
    if minutes < 0:
        raise contract.RequestError("[web] unload_after (or AIGEN_UNLOAD_AFTER) is %r; expected the minutes, an"
                                    " integer (0: never)" % text)
    return minutes


def boolean(text, name):
    """true/yes/1/on or false/no/0/off (any case) as a bool; anything else is a RequestError naming the key."""
    value = text.strip().lower()
    if value in TRUE:
        return True
    if value in FALSE:
        return False
    raise contract.RequestError("%s is %r; expected true or false (yes/no, 1/0, on/off)" % (name, text))


def read(root=ROOT, environ=None):
    """Reads config.ini and config.local.ini from `root` and the AIGEN_* variables from `environ` (default:
    os.environ)."""
    environ = os.environ if environ is None else environ
    ini = configparser.ConfigParser(interpolation=None)
    try:
        ini.read([os.path.join(root, "config.ini"), os.path.join(root, "config.local.ini")], encoding="utf-8")
    except configparser.Error as e:
        raise contract.RequestError("config.ini (or config.local.ini) could not be read: %s" % e)
    values = {}
    for name, (section, key, variable, default, is_path) in KEYS.items():
        value = environ.get(variable)
        if value is None:
            value = ini.get(section, key, fallback=default)
        values[name] = _path(value, root) if is_path else value.strip()
    values["port"] = _port(values["port"])
    values["save_prompts"] = boolean(values["save_prompts"], "[privacy] save_prompts (or AIGEN_SAVE_PROMPTS)")
    values["unload_after"] = _minutes(values["unload_after"])
    return Config(values)
