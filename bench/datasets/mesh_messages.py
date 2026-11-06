"""Build data/mesh_messages/<lang>/manifest.csv from your recordings.

    python -m bench.datasets.mesh_messages --lang fr en
"""
import argparse
import sys

from .common import wav_duration, write_manifest
from .prompts import MESH, load_prompts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", nargs="+", default=["fr", "en"])
    a = ap.parse_args(argv)
    for lang in a.lang:
        rows, missing = [], []
        for pid, text in load_prompts(lang):
            p = MESH / lang / f"{pid}.wav"
            if p.exists():
                rows.append(dict(utt_id=f"mesh-{pid}", path=p, duration=wav_duration(p),
                                 reference=text, language=lang))
            else:
                missing.append(pid)
        if not rows:
            print(f"{lang}: no recordings in {MESH / lang}; run bench.datasets.record first")
            continue
        path = write_manifest(rows, MESH / lang / "manifest.csv")
        print(f"{lang}: {len(rows)} recordings -> {path}" + (f" (missing: {' '.join(missing)})" if missing else ""))


if __name__ == "__main__":
    sys.exit(main())
