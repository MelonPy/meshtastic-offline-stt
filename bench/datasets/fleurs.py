"""Download the FLEURS test split (google/fleurs) and build a manifest.

    python -m bench.datasets.fleurs --lang fr en [--limit 20]

Files are fetched from the dataset's Hugging Face repo at a pinned revision and
checked against the SHA256 that Hugging Face publishes for them (LFS oid).
Audio is converted to 16 kHz mono 16-bit WAV here, once, outside any timing.
Output: data/fleurs/<lang>/wav/*.wav and data/fleurs/<lang>/manifest.csv

Ordering: the first recording of every sentence comes first (in FLEURS order),
then the remaining recordings, so --limit N gives N different sentences.

FLEURS is licensed CC-BY-4.0 (https://huggingface.co/datasets/google/fleurs).
"""
import argparse
import csv
import shutil
import sys
import tarfile
from pathlib import Path

from .common import DATA, download, to_wav16k, wav_duration, write_manifest

REPO = "google/fleurs"
REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/data"
CONFIGS = {
    # lang: (fleurs config, test.tar.gz sha256)
    "fr": ("fr_fr", "d23690e102f373554d1b544cd2ff1e76e4fedeb04953c0b72751a1b7c518cfdd"),
    "en": ("en_us", "d9c2e37b41aacd41bc283554a0a82b5476b36887049774ecb2819dcaaa55a356"),
}


def ordered_rows(tsv_path):
    with open(tsv_path, encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    first, rest, seen = [], [], set()
    for r in rows:
        sent_id, file_name, raw = r[0], r[1], r[2]
        item = (sent_id, file_name, raw)
        (rest if sent_id in seen else first).append(item)
        seen.add(sent_id)
    return first + rest


def prepare(lang, limit=None, keep_archive=True):
    cfg, tar_sha = CONFIGS[lang]
    out = DATA / "fleurs" / lang
    dl = DATA / "downloads" / "fleurs" / cfg
    tsv = download(f"{BASE}/{cfg}/test.tsv", dl / "test.tsv")
    rows = ordered_rows(tsv)
    if limit:
        rows = rows[:limit]
    wav_dir = out / "wav"
    todo = [r for r in rows if not (wav_dir / r[1]).exists()]
    if todo:
        tar_path = download(f"{BASE}/{cfg}/audio/test.tar.gz", dl / "test.tar.gz", tar_sha)
        wanted = {r[1] for r in todo}
        raw_dir = dl / "raw"
        with tarfile.open(tar_path) as tf:
            for m in tf:
                name = Path(m.name).name
                if m.isfile() and name in wanted:
                    m.name = name
                    tf.extract(m, raw_dir, filter="data")
        for _, fname, _ in todo:
            to_wav16k(raw_dir / fname, wav_dir / fname)
        shutil.rmtree(raw_dir, ignore_errors=True)
        if not keep_archive:
            tar_path.unlink()
    manifest = []
    for sent_id, fname, raw in rows:
        p = wav_dir / fname
        manifest.append(dict(utt_id=f"fleurs-{lang}-{sent_id}-{Path(fname).stem}", path=p,
                             duration=wav_duration(p), reference=raw, language=lang))
    name = f"manifest_limit{limit}.csv" if limit else "manifest.csv"
    path = write_manifest(manifest, out / name)
    total = sum(r["duration"] for r in manifest)
    print(f"{lang}: {len(manifest)} utterances, {total / 60:.1f} min -> {path}")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", nargs="+", default=["fr", "en"], choices=sorted(CONFIGS))
    ap.add_argument("--limit", type=int, default=None, help="only the first N utterances")
    ap.add_argument("--delete-archive", action="store_true", help="remove the .tar.gz after extraction")
    a = ap.parse_args(argv)
    for lang in a.lang:
        prepare(lang, a.limit, keep_archive=not a.delete_archive)


if __name__ == "__main__":
    sys.exit(main())
