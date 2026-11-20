"""The LoRAs: finding the file in the folder, reading the "name:weight" list from the command line and the web
interface, and turning them on in the pipeline.

Only the stage uses diffusers (through the pipeline it receives); the rest is pure.
"""
import os
import re

from aigen import contract, stages

EXTENSION = ".safetensors"


def find_file(folder, name):
    """The file of the LoRA `name` in the folder (with or without the .safetensors extension), or None."""
    for candidate in (name, name + EXTENSION):
        path = os.path.join(folder, candidate)
        if candidate.endswith(EXTENSION) and os.path.isfile(path):
            return path
    return None


def list_loras(folder):
    """The names (without .safetensors) of the LoRAs in the folder and its subfolders, sorted; [] if the folder does not
    exist."""
    if not os.path.isdir(folder):
        return []
    names = []
    for dirpath, _, files in os.walk(folder):
        for n in files:
            if n.endswith(EXTENSION):
                relative = os.path.relpath(os.path.join(dirpath, n), folder)
                names.append(relative[:-len(EXTENSION)].replace(os.sep, "/"))
    return sorted(names)


def parse_list(text):
    """The LoRA list of a "name:weight" text, one per line or comma-separated; without ":weight", the weight is 1."""
    loras = []
    for item in re.split(r"[\n,]", text or ""):
        item = item.strip()
        if not item:
            continue
        name, _, weight = item.rpartition(":") if ":" in item else (item, "", "1")
        try:
            value = float(weight)
        except ValueError:
            raise contract.RequestError("the LoRA '%s' has the weight '%s'; expected a number (name:weight)"
                                        % (item, weight))
        loras.append({"name": name.strip(), "weight": value})
    return contract.check_loras(loras, "the LoRA list")


def adapter_name(name):
    """An adapter name diffusers accepts (no dots or slashes)."""
    return "lora_" + re.sub(r"[^0-9A-Za-z_]", "_", name)


@stages.declare(reads=("pipe", "loras", "session", "cfg", "report"), writes=("active_loras",))
def stage(t):
    """Turns on the requested LoRAs with their weights. The loaded ones stay in the session: they are reloaded only
    when the list changes."""
    pipe, session = t.pipe, t.session
    names = [l["name"] for l in t.loras]
    if sorted(names) != sorted(session.loaded_loras):
        if session.loaded_loras:
            pipe.unload_lora_weights()
            session.loaded_loras = ()
        for name in names:
            path = find_file(t.cfg.loras_folder, name)
            pipe.load_lora_weights(os.path.dirname(path), weight_name=os.path.basename(path),
                                   adapter_name=adapter_name(name))
        session.loaded_loras = tuple(names)
    if names:
        pipe.set_adapters([adapter_name(n) for n in names], adapter_weights=[l["weight"] for l in t.loras])
    t.active_loras = [dict(l) for l in t.loras]
    t.report["loras"] = t.active_loras
