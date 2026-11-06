"""Download the FLEURS test split (google/fleurs) and build a manifest.

    python -m bench.datasets.fleurs --lang fr en [--limit 20]

Files are fetched from the dataset's Hugging Face repo at a pinned revision and
checked against the SHA256 that Hugging Face publishes for them (LFS oid).
Audio is converted to 16 kHz mono 16-bit WAV here, once, outside any timing.
Output: data/fleurs/<lang>/wav/*.wav and data/fleurs/<lang>/manifest.csv

Ordering: the first recording of every sentence comes first (in FLEURS order),
then the remaining recordings, so --limit N gives N different sentences.

Peak normalisation (opt-in, off by default):

    python -m bench.datasets.fleurs --lang en --normalize-peak -3

Many FLEURS recordings are very quiet (en_us: median peak about 0.009 of full
scale, i.e. about -41 dBFS; fr_fr: about 0.25). Level-sensitive engines then drop
words, which a real microphone chain with gain control would avoid. With
--normalize-peak DBFS each utterance is scaled so that its peak sample sits at
DBFS (one linear gain per file, so no clipping and no compression), with the
gain capped at --max-gain-db (default 40 dB) so near-silent files are not blown
up into noise. The result is a SEPARATE dataset next to the raw one:

    data/fleurs/<lang>_peak<DBFS>dB/wav/*.wav, manifest.csv, gains.csv

and the raw set is never modified. Use it with dataset name "fleurs-peak<DBFS>dB"
(see configs/smoke_peaknorm.yaml) so results are never confused with raw FLEURS.

FLEURS is licensed CC-BY-4.0 (https://huggingface.co/datasets/google/fleurs).
"""
import argparse
import csv
import shutil
import sys
import tarfile
import wave
from pathlib import Path

import numpy as np

from .common import DATA, download, read_manifest, to_wav16k, wav_duration, write_manifest

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


def peak_dir_name(lang, target_dbfs):
    return f"{lang}_peak{target_dbfs:g}dB"


def normalise_peak(lang, manifest_path, target_dbfs=-3.0, max_gain_db=40.0, limit=None):
    """Write a peak-normalised copy of the utterances in manifest_path (see module doc)."""
    if target_dbfs > 0:
        raise ValueError("--normalize-peak must be <= 0 dBFS")
    out = DATA / "fleurs" / peak_dir_name(lang, target_dbfs)
    target = 32767 * 10 ** (target_dbfs / 20)
    max_gain = 10 ** (max_gain_db / 20)
    rows, gains = [], []
    for r in read_manifest(manifest_path, limit):
        with wave.open(r["path"], "rb") as w:
            params = w.getparams()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        peak = int(np.abs(x.astype(np.int32)).max()) if x.size else 0
        gain = min(target / peak, max_gain) if peak else 1.0
        y = np.clip(np.round(x.astype(np.float64) * gain), -32768, 32767).astype(np.int16)
        dst = out / "wav" / Path(r["path"]).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dst), "wb") as w:
            w.setparams(params)
            w.writeframes(y.tobytes())
        rows.append(dict(r, path=dst))
        gains.append((r["utt_id"], peak / 32768, 20 * np.log10(gain), gain == max_gain))
    name = f"manifest_limit{limit}.csv" if limit else "manifest.csv"
    path = write_manifest(rows, out / name)
    with open(out / "gains.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "original_peak", "gain_db", "gain_capped"])
        for uid, pk, gdb, capped in gains:
            w.writerow([uid, f"{pk:.5f}", f"{gdb:.2f}", int(capped)])
    g = sorted(x[2] for x in gains)
    capped = sum(x[3] for x in gains)
    print(f"{lang}: peak-normalised to {target_dbfs:g} dBFS, median gain {g[len(g) // 2]:+.1f} dB, "
          f"{capped} capped at +{max_gain_db:g} dB -> {path}")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", nargs="+", default=["fr", "en"], choices=sorted(CONFIGS))
    ap.add_argument("--limit", type=int, default=None, help="only the first N utterances")
    ap.add_argument("--delete-archive", action="store_true", help="remove the .tar.gz after extraction")
    ap.add_argument("--normalize-peak", type=float, metavar="DBFS", default=None,
                    help="also write a peak-normalised copy (e.g. -3); off by default")
    ap.add_argument("--max-gain-db", type=float, default=40.0,
                    help="cap on the normalisation gain (default 40 dB)")
    a = ap.parse_args(argv)
    for lang in a.lang:
        manifest = prepare(lang, a.limit, keep_archive=not a.delete_archive)
        if a.normalize_peak is not None:
            normalise_peak(lang, manifest, a.normalize_peak, a.max_gain_db, a.limit)


if __name__ == "__main__":
    sys.exit(main())
