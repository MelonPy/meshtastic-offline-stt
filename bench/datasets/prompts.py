from pathlib import Path

from .common import DATA

MESH = DATA / "mesh_messages"


def load_prompts(lang):
    out = []
    for line in (MESH / f"prompts_{lang}.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        pid, text = line.split("\t", 1)
        out.append((pid.strip(), text.strip()))
    return out
