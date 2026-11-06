#!/usr/bin/env bash
# Set up a benchmark host (dev x86_64 machine or the Radxa ZERO 3W, aarch64).
#  - creates .venv/ and installs the pinned Python dependencies
#  - clones whisper.cpp at a pinned release and builds whisper-cli
# System packages are NOT installed automatically; missing ones are reported.
set -euo pipefail

WHISPER_CPP_TAG="v1.9.5"
WHISPER_CPP_COMMIT="d1be6fde11ac6e0407606b4e42fe72d34add8037"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== Checking system tools"
missing=()
for t in python3 git cmake make gcc g++ ffmpeg taskset unshare; do
  command -v "$t" >/dev/null 2>&1 || missing+=("$t")
done
if ((${#missing[@]})); then
  echo "Missing tools: ${missing[*]}"
  echo "On Debian/Ubuntu: sudo apt install python3-venv git cmake build-essential ffmpeg util-linux"
  exit 1
fi
# Optional: only needed by bench/datasets/record.py (microphone capture)
python3 - <<'PY' || echo "Note: PortAudio not found; install libportaudio2 to use record.py"
import ctypes.util, sys
sys.exit(0 if ctypes.util.find_library("portaudio") else 1)
PY

echo "== Python venv"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "== whisper.cpp ${WHISPER_CPP_TAG}"
WDIR="third_party/whisper.cpp"
if [ ! -d "$WDIR/.git" ]; then
  git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$WHISPER_CPP_TAG" https://github.com/ggml-org/whisper.cpp "$WDIR"
fi
actual="$(git -C "$WDIR" rev-parse HEAD)"
if [ "$actual" != "$WHISPER_CPP_COMMIT" ]; then
  echo "ERROR: whisper.cpp is at $actual, expected $WHISPER_CPP_COMMIT ($WHISPER_CPP_TAG)" >&2
  exit 1
fi
# GGML_NATIVE=ON tunes the build for the CPU it runs on (e.g. AVX2 on x86, NEON/dotprod
# on the Cortex-A55), so always build ON the device you benchmark.
cmake -S "$WDIR" -B "$WDIR/build" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON \
      -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DBUILD_SHARED_LIBS=OFF >/dev/null
cmake --build "$WDIR/build" --config Release -j"$(nproc)" --target whisper-cli >/dev/null
"$WDIR/build/bin/whisper-cli" --help >/dev/null 2>&1 || true
echo "whisper-cli: $ROOT/$WDIR/build/bin/whisper-cli"

echo "== Done. Next: scripts/fetch_models.sh"
