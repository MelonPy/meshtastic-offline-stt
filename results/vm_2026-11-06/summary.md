# Benchmark results: smoke

> **DEV-HOST BASELINE - not RK3566 numbers**

- Host: Intel(R) Xeon(R) Processor @ 2.10GHz (x86_64, 4 cores, 15.71 GiB RAM), Ubuntu 24.04.5 LTS, kernel 6.18.44-fc-v242
- Date: 2026-11-06T09:19:34+00:00 · repo commit `0b3a6713a1`
- Network isolation: unshare -rn: no network inside the namespace
- Pinned CPUs: `0-3` · warm-up utterances per run: 1

WER/CER are corpus-level on normalised text (see `bench/metrics.py`); raw = only whitespace normalised. RTF = inference time / audio duration, model load excluded. Latency p90 = end of audio → final text (offline engines: whole-utterance processing time; streaming engines: time after the last chunk was fed). Peak RAM = max RSS of the engine process.

| Engine | Model | Lang | Mode | Thr | N | WER | CER | WER raw | RTF mean | RTF p90 | Latency p90 (s) | Load (s) | Peak RAM (MB) | Model (MB) | CPU % | Offline |
|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| whisper_cpp | whisper-tiny | fr | offline | 4 | 20 | 38.6% | 14.8% | 42.8% | 0.106 | 0.136 | 1.37 | 0.08 | 176 | 78 | 85.3% | yes |
| whisper_cpp | whisper-tiny | en | offline | 4 | 20 | 13.8% | 6.4% | 20.8% | 0.077 | 0.100 | 0.81 | 0.09 | 176 | 78 | 83.5% | yes |
| whisper_cpp | whisper-tiny-q5_1 | fr | offline | 4 | 20 | 38.6% | 14.8% | 43.4% | 0.132 | 0.169 | 1.60 | 0.05 | 133 | 32 | 89.4% | yes |
| whisper_cpp | whisper-tiny-q5_1 | en | offline | 4 | 20 | 13.5% | 6.5% | 22.6% | 0.102 | 0.127 | 1.03 | 0.05 | 132 | 32 | 88.1% | yes |
| whisper_cpp | whisper-tiny-q8_0 | fr | offline | 4 | 20 | 38.8% | 15.3% | 42.2% | 0.096 | 0.118 | 1.26 | 0.06 | 146 | 44 | 86.7% | yes |
| whisper_cpp | whisper-tiny-q8_0 | en | offline | 4 | 20 | 14.9% | 6.9% | 23.1% | 0.072 | 0.093 | 0.76 | 0.06 | 145 | 44 | 85.8% | yes |
| whisper_cpp | whisper-base | fr | offline | 4 | 20 | 24.5% | 9.0% | 31.5% | 0.210 | 0.277 | 2.55 | 0.13 | 283 | 148 | 86.8% | yes |
| whisper_cpp | whisper-base | en | offline | 4 | 20 | 8.8% | 4.5% | 15.2% | 0.166 | 0.219 | 1.67 | 0.14 | 282 | 148 | 84.6% | yes |

Power: not measured automatically. Use `--power-prompt` with a USB power meter or `python -m bench.power` to add readings.
