import json
from pathlib import Path

from .paths import ROOT as BASE, STATE
SETTINGS = STATE / "settings.json"
DEFAULTS = {"width": 1024, "height": 768, "quality": 6, "rotation": 0, "adaptive": 1}


def load():
    values = dict(DEFAULTS)
    if SETTINGS.exists():
        values.update(json.loads(SETTINGS.read_text()))
    for key, low, high in (("width", 320, 1024), ("height", 240, 768),
                           ("quality", 0, 10), ("rotation", 0, 3), ("adaptive",0,1)):
        if type(values[key]) is not int or not low <= values[key] <= high:
            raise ValueError("Invalid monitor setting: " + key)
    return values


def save(values):
    temporary = SETTINGS.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, indent=2) + "\n")
    temporary.replace(SETTINGS)
