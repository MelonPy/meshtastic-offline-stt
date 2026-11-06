"""Common Voice importer (manual download required).

Common Voice cannot be fetched without manual steps: releases are distributed by
the Mozilla Data Collective (https://datacollective.mozillafoundation.org), which
requires an account and accepting the dataset terms before download, and the old
Hugging Face mirrors (mozilla-foundation/common_voice_*) are gated. So this
script does not download anything. Once you have downloaded and extracted a
release yourself, point it at the language folder (the one holding clips/ and
test.tsv):

    python -m bench.datasets.common_voice --src ~/cv-corpus-XX/fr --lang fr [--limit 20]

It converts the test-split MP3s to 16 kHz mono WAV and writes
data/common_voice/<lang>/manifest.csv. Record the release name/version you used.
"""
import argparse
import csv
import sys
from pathlib import Path

from .common import DATA, to_wav16k, wav_duration, write_manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=Path, help="extracted Common Voice language folder")
    ap.add_argument("--lang", required=True, choices=["fr", "en"])
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    tsv = a.src / f"{a.split}.tsv"
    if not tsv.exists():
        sys.exit(f"not found: {tsv}")
    with open(tsv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    rows = rows[: a.limit] if a.limit else rows
    out = DATA / "common_voice" / a.lang
    manifest = []
    for r in rows:
        src = a.src / "clips" / r["path"]
        dst = out / "wav" / (Path(r["path"]).stem + ".wav")
        if not dst.exists():
            to_wav16k(src, dst)
        manifest.append(dict(utt_id=f"cv-{a.lang}-{Path(r['path']).stem}", path=dst,
                             duration=wav_duration(dst), reference=r["sentence"], language=a.lang))
    name = f"manifest_limit{a.limit}.csv" if a.limit else "manifest.csv"
    print(write_manifest(manifest, out / name))


if __name__ == "__main__":
    sys.exit(main())
