"""Shared dataset helpers: download with checksum, ffmpeg conversion, manifests."""
import csv
import hashlib
import subprocess
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST_FIELDS = ["utt_id", "path", "duration", "reference", "language"]


def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(bufsize):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, sha256=None):
    """Download url to dest (skipped if present) and check sha256. Raises on mismatch."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        print(f"downloading {url}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    if sha256:
        got = sha256_file(dest)
        if got != sha256:
            dest.unlink()
            raise RuntimeError(f"SHA256 mismatch for {dest.name}: expected {sha256}, got {got}")
    return dest


def to_wav16k(src, dst):
    """Convert any audio file to 16 kHz mono signed 16-bit PCM WAV with ffmpeg."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", "-c:a", "pcm_s16le", str(dst)],
        check=True)
    return dst


def wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def write_manifest(rows, path):
    """rows: dicts with MANIFEST_FIELDS; 'path' is stored relative to the repo root."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in rows:
            r = dict(r)
            p = Path(r["path"])
            if p.is_absolute():
                try:
                    r["path"] = str(p.relative_to(ROOT))
                except ValueError:
                    r["path"] = str(p)
            r["duration"] = f"{float(r['duration']):.3f}"
            w.writerow(r)
    return path


def read_manifest(path, limit=None):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        p = Path(r["path"])
        r["path"] = str(p if p.is_absolute() else ROOT / p)
        r["duration"] = float(r["duration"])
    return rows[:limit] if limit else rows
