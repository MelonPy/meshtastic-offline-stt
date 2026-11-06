#!/usr/bin/env bash
# One-shot benchmark for a fresh host (meant for the Radxa ZERO 3W):
# setup -> fetch + verify models -> prepare FLEURS -> smoke test -> full run.
#
#   scripts/run_radxa.sh            # everything
#   scripts/run_radxa.sh --smoke    # stop after the 20-utterance smoke test
#
# Downloads need network; the benchmark itself runs with the network removed.
# Expect several hours for the full run on the RK3566 (whisper-small is slow).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

scripts/setup_host.sh
scripts/fetch_models.sh
.venv/bin/python -m bench.datasets.fleurs --lang fr en

.venv/bin/python -m bench.run --config configs/smoke.yaml --out "results/$(hostname)_$(date +%F)_smoke"
[ "${1:-}" = "--smoke" ] && exit 0
.venv/bin/python -m bench.run --config configs/full.yaml
.venv/bin/python -m bench.run --config configs/threads.yaml --out "results/$(hostname)_$(date +%F)_threads"
