#!/usr/bin/env python3
"""Generate configs/models.lock.json: the pinned list of every model file.

Run this only when you want to add or bump a model. It records, per file:
URL (pinned to a commit/revision where the host supports it), size, SHA256 and
where that SHA256 came from:

  - "hf-lfs":  published by Hugging Face (LFS object id == SHA256 of the file)
  - "tofu":    no checksum is published upstream; the file was downloaded once
               and hashed ("trust on first use"). Later downloads must match.

scripts/fetch_models.sh then downloads and verifies against this lock and never
trusts the network again. Uses only the standard library.
"""
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "configs" / "models.lock.json"

HF = "https://huggingface.co"

# ---------------------------------------------------------------------------
# Model specification. Revisions are git commits of the Hugging Face repos,
# checked on 2026-11-06.
# ---------------------------------------------------------------------------
WHISPER_REPO, WHISPER_REV = "ggerganov/whisper.cpp", "5359861c739e955e79d9a303bcbc70fb988958b1"
SPEC = []

for name in ["tiny", "tiny-q5_1", "tiny-q8_0", "base", "base-q5_1", "base-q8_0", "small"]:
    SPEC.append(dict(
        id=f"whisper-{name}", engine="whisper_cpp", langs=["fr", "en"],
        source=f"{HF}/{WHISPER_REPO}", revision=WHISPER_REV,
        licence="MIT (OpenAI Whisper weights, ggml conversion by ggerganov)",
        hf=dict(repo=WHISPER_REPO, rev=WHISPER_REV, files=[f"ggml-{name}.bin"]),
    ))

SPEC += [
    dict(id="vosk-small-fr-0.22", engine="vosk", langs=["fr"],
         source="https://alphacephei.com/vosk/models", revision="0.22",
         licence="Apache-2.0",
         url_files=[("vosk-model-small-fr-0.22.zip",
                     "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip")],
         unpack="zip"),
    dict(id="vosk-small-en-us-0.15", engine="vosk", langs=["en"],
         source="https://alphacephei.com/vosk/models", revision="0.15",
         licence="Apache-2.0",
         url_files=[("vosk-model-small-en-us-0.15.zip",
                     "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")],
         unpack="zip"),
]

for lang, rev in [("fr", "08b84b7b7cf519be9817e9c16919d96a7a8bad91"),
                  ("en", "572aaf4e2e0c603c3fc2a574d096e755a178faa1")]:
    repo = f"csukuangfj/sherpa-onnx-streaming-zipformer-{lang}-kroko-2025-08-06"
    SPEC.append(dict(
        id=f"sherpa-zipformer-{lang}-kroko-2025-08-06", engine="sherpa_onnx", langs=[lang],
        source=f"{HF}/{repo} (k2-fsa release asr-models; upstream https://huggingface.co/Banafo/Kroko-ASR)",
        revision=rev,
        licence="CC-BY-SA (Kroko 'Community' model, per https://huggingface.co/Banafo/Kroko-ASR)",
        hf=dict(repo=repo, rev=rev, files=["encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt"]),
    ))

MOONSHINE_FILES = ["onnx/encoder_model.onnx", "onnx/decoder_model_merged.onnx",
                   "tokenizer.json", "config.json", "generation_config.json",
                   "preprocessor_config.json"]
for mid, lang, repo, rev, lic in [
    ("moonshine-tiny-en", "en", "onnx-community/moonshine-tiny-ONNX",
     "a6da1241cd305dcd64eab1edbd615f2bb9aabb95", "MIT (UsefulSensors/moonshine-tiny, ONNX export by onnx-community)"),
    ("moonshine-base-en", "en", "onnx-community/moonshine-base-ONNX",
     "b1e9b6aae3c3c7298f10c3798393fdf38e8fbbad", "MIT (UsefulSensors/moonshine-base, ONNX export by onnx-community)"),
    ("moonshine-tiny-fr", "fr", "onnx-community/moonshine-tiny-fr-ONNX",
     "45f68dff4a8855aad3b965e1ee312c3187fcd767",
     "MIT (community fine-tune Cornebidouil/moonshine-tiny-fr, rev cae6a667; ONNX export by onnx-community)"),
]:
    SPEC.append(dict(id=mid, engine="moonshine", langs=[lang], source=f"{HF}/{repo}",
                     revision=rev, licence=lic,
                     hf=dict(repo=repo, rev=rev, files=MOONSHINE_FILES)))


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def hash_download(url):
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(url, timeout=120) as r:
        while chunk := r.read(1 << 20):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def hf_entries(repo, rev, files):
    tree = {}
    dirs = {os.path.dirname(f) for f in files}
    for d in dirs:
        api = f"{HF}/api/models/{repo}/tree/{rev}" + (f"/{d}" if d else "")
        for e in get_json(api):
            tree[e["path"]] = e
    out = []
    for f in files:
        e = tree[f]
        url = f"{HF}/{repo}/resolve/{rev}/{f}"
        if e.get("lfs"):
            sha, size, src = e["lfs"]["oid"], e["lfs"]["size"], "hf-lfs"
        else:
            sha, size = hash_download(url)
            src = "tofu"
        out.append(dict(path=f, url=url, size=size, sha256=sha, sha256_source=src))
    return out


def main():
    models = []
    for m in SPEC:
        print("locking", m["id"], file=sys.stderr)
        entry = {k: v for k, v in m.items() if k not in ("hf", "url_files")}
        if "hf" in m:
            entry["files"] = hf_entries(**m["hf"])
        else:
            entry["files"] = []
            for fname, url in m["url_files"]:
                sha, size = hash_download(url)
                entry["files"].append(dict(path=fname, url=url, size=size, sha256=sha,
                                           sha256_source="tofu"))
        models.append(entry)
    LOCK.write_text(json.dumps({"generated": "scripts/lock_models.py", "models": models},
                               indent=2) + "\n")
    print("wrote", LOCK, file=sys.stderr)


if __name__ == "__main__":
    main()
