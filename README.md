# Meshtastic Offline STT

**Secure, offline, multilingual speech-to-text for Meshtastic, running on the Radxa ZERO 3W.**

> Status: early stage — project plan and benchmark design.

## Goal

[Meshtastic](https://meshtastic.org) lets people exchange text messages over LoRa without internet or cell coverage. LoRa's bandwidth is far too low to carry voice, so users have to type on a phone or a tiny keypad.

This project lets a user **dictate a message, transcribe it locally on the device with no internet connection, and send it as text over the mesh**. French comes first, followed by other languages.

## Design principles

- **Fully offline:** no cloud API, no network needed for recognition.
- **Privacy by design:** audio never leaves the device and is never stored by default.
- **Secure embedded system:** hardened Linux image and protected data and models, so a lost or captured node exposes as little as possible.
- **Open and reproducible:** every benchmark comes with scripts, model versions and settings.

## Architecture (planned)

```
 ┌──────────────┐   audio   ┌──────────────────────────┐   text   ┌────────────────┐   LoRa
 │  Microphone  │ ────────► │  Radxa ZERO 3W (RK3566)  │ ───────► │ Meshtastic node│ ~~~~~~► mesh
 │ (USB / I2S)  │           │  VAD → STT → text cleanup│  serial  │ (USB or SPI    │
 └──────────────┘           └──────────────────────────┘          │  LoRa module)  │
                                                                  └────────────────┘
```

The ZERO 3W handles audio capture, voice activity detection and speech recognition. The text is passed to Meshtastic, either through a Meshtastic node connected over USB serial or through a LoRa module wired to the board.

## Hardware

- Radxa ZERO 3W — RK3566, 4 GB LPDDR4, 32 GB eMMC (RS107-D4E32H1W15)
- Microphone (USB or I2S)
- Meshtastic-compatible LoRa node or module

## Speech models to benchmark

| Engine | Why |
|---|---|
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | Strong multilingual accuracy; tiny / base / small models |
| [Vosk](https://alphacephei.com/vosk/) | Lightweight, streaming, small per-language models |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Streaming models, ONNX runtime, good ARM support |
| [Moonshine](https://github.com/usefulsensors/moonshine) | Designed for low-latency on-device recognition |

**Languages:** French first, then English, then additional languages.

**Metrics:**
- Accuracy: word error rate (WER), or character error rate (CER) for languages without spaces
- Speed: real-time factor and end-to-end latency (end of speech → text ready)
- Resources: peak RAM, model size on eMMC, CPU load, power draw

**Test data:** public multilingual speech datasets (e.g. Mozilla Common Voice, FLEURS), plus short dictated messages typical of mesh use.

## Security and hardening (planned)

- Minimal Linux image with unused services removed
- Encrypted storage for user data and configuration
- Integrity protection for models and binaries
- Locked-down remote access and firewall
- A documented threat model covering a lost or captured node

Each measure will be documented with how to reproduce it and its cost in performance or power.

## Roadmap

This is an exploration project developed alongside engineering studies and an
apprenticeship, so it advances in phases rather than on fixed dates.

**Phase 1 — Benchmarks (first)**
Set the board up, run the four engines on French and English samples, and publish
accuracy, latency, memory and power figures with the scripts used to produce them.

**Phase 2 — Hardening**
Document the threat model and the hardening measures, with their cost in
performance and power.

**Phase 3 — Mesh integration (from January 2027)**
Wire the transcription output into a mesh transport — Meshtastic, and possibly
MeshCore — for a first end-to-end prototype.

Results are shared on the Radxa forum as each phase completes.

## Running the benchmarks

The Phase 1 harness lives in `bench/`. It runs the same way on a development PC
and on the Radxa ZERO 3W. Results from a machine other than the board are
labelled **dev-host baselines** and are not RK3566 numbers.

### Layout

```
bench/engines/    one adapter per engine (whisper.cpp, Vosk, sherpa-onnx, Moonshine)
bench/datasets/   FLEURS download, Common Voice importer, mesh-message recorder
bench/metrics.py  WER/CER (with documented text normalisation), RTF, latency
bench/run.py      CLI entry point; bench/worker.py runs one engine per process
configs/          benchmark matrices (YAML) and models.lock.json (pinned models)
scripts/          setup_host.sh, fetch_models.sh, run_radxa.sh
results/          results.json / summary.csv / summary.md per run (raw logs gitignored)
models/ data/     downloaded models and audio (gitignored)
```

### 1. Set up the host

Requirements: Python 3.11+, git, cmake, a C/C++ compiler, ffmpeg, util-linux
(`taskset`, `unshare`); optional `strace` (network-attempt check) and
`libportaudio2` (recording). On Debian/Ubuntu:

```bash
sudo apt install python3-venv git cmake build-essential ffmpeg util-linux strace libportaudio2
```

```bash
scripts/setup_host.sh
```

This creates `.venv/` with the pinned `requirements.txt` and builds `whisper-cli`
from whisper.cpp v1.9.5 on the machine itself.

### 2. Fetch and verify the models

```bash
scripts/fetch_models.sh
```

Every file listed in `configs/models.lock.json` is downloaded from a pinned
revision and checked against its SHA256. A mismatch deletes the file and makes
the script fail. `scripts/fetch_models.sh --verify` re-checks what is on disk,
and `bench.run` re-hashes the model files before each run. The lock records the
source, revision, licence and size of each model. Where upstream publishes no
checksum (the Vosk zips and a few small JSON/text files), the SHA256 was recorded
on first download (`sha256_source: tofu`).

| Engine | Models | Languages |
|---|---|---|
| whisper.cpp | ggml tiny, base, small; tiny/base in q5_1 and q8_0 (no multilingual q5_0 files are published) | fr, en |
| Vosk | vosk-model-small-fr-0.22, vosk-model-small-en-us-0.15 | fr / en |
| sherpa-onnx | streaming zipformer "kroko" 2025-08-06, fr and en (Banafo Kroko community models, CC-BY-SA) | fr / en |
| Moonshine | tiny, base (English); tiny-fr (community fine-tune `Cornebidouil/moonshine-tiny-fr`, MIT), all as onnx-community ONNX exports | en / fr |

### 3. Prepare the test data

```bash
.venv/bin/python -m bench.datasets.fleurs --lang fr en
```

This downloads the FLEURS test split (`google/fleurs`, pinned revision, checksum
verified, CC-BY-4.0) and converts it once to 16 kHz mono WAV. It writes
`data/fleurs/<lang>/manifest.csv` (path, duration, reference, language).

Many FLEURS recordings are very quiet (en_us: median peak about -41 dBFS), and
level-sensitive engines then drop words. To test with levels closer to a real
microphone chain, you can also create a peak-normalised copy (opt-in; the raw set
stays the default and is never modified):

```bash
.venv/bin/python -m bench.datasets.fleurs --lang fr en --normalize-peak -3
```

```bash
.venv/bin/python -m bench.run --config configs/smoke_peaknorm.yaml
```

Each file gets one linear gain that puts its peak at -3 dBFS, capped at +40 dB
(`--max-gain-db`). The copy goes to `data/fleurs/<lang>_peak-3dB/`, with the gain
of each file in `gains.csv`, and results are labelled `fleurs-peak-3dB`. Common
Voice needs a manual download (see `bench/datasets/common_voice.py`). To record
your own mesh-style messages, see
[`data/mesh_messages/README.md`](data/mesh_messages/README.md).

### 4. Smoke test, then the full run

```bash
.venv/bin/python -m bench.run --config configs/smoke.yaml
```

```bash
.venv/bin/python -m bench.run --config configs/full.yaml
```

```bash
.venv/bin/python -m bench.run --config configs/threads.yaml
```

The smoke test uses the first 20 utterances per language; `--limit N`,
`--threads 1 2 4` and `--only <model>` override the config. Each run writes
`results/<host>_<date>/results.json`, `summary.csv` and `summary.md`.

On the board, `scripts/run_radxa.sh` does steps 1–4 in one go.

### How the measurements are taken

- **Isolation:** each engine/model/language/thread job runs in its own process,
  pinned with `taskset -c 0-3`, inside a network namespace with no network
  (`unshare -rn`), with `HF_HUB_OFFLINE=1`. A Python audit hook records socket
  use, and one pass per model under `strace` catches network calls from native
  code. Any attempt marks the run "Offline: NO". If unprivileged user namespaces
  are disabled, enable them (`sudo sysctl kernel.unprivileged_userns_clone=1`) or
  pass `--allow-network` (the run is then not marked offline).
- **Accuracy:** corpus-level WER and CER with jiwer, both raw and normalised.
  Normalisation (lowercase, apostrophes and hyphens to spaces, punctuation
  removed, whitespace collapsed) is applied identically to reference and
  hypothesis and is documented in `bench/metrics.py`. Numbers are not converted,
  so "100" against "one hundred" counts as an error.
- **Speed:** RTF = inference time / audio duration, model load excluded (load
  time is reported separately); mean and p90 over utterances. For whisper.cpp,
  whisper-cli runs once per utterance and its own timings (total − load) are used.
- **Latency:** for streaming engines (Vosk, sherpa-onnx), the time from feeding
  the last 100 ms chunk to the final text. For whole-utterance engines, it is the
  processing time of the utterance.
- **Memory / CPU:** peak RSS of the engine process (kernel high-water mark), and
  CPU time / wall time / number of pinned CPUs.
- **Power:** not measured automatically. Pass `--power-prompt` to enter USB power
  meter readings after each run, or add them later with `python -m bench.power`.
- **Metadata:** every `results.json` embeds the CPU, architecture, cores, RAM, OS,
  kernel, engine and package versions, model SHA256s, the git commit of this repo
  and the config used.

## License

MIT — see [LICENSE](LICENSE).
