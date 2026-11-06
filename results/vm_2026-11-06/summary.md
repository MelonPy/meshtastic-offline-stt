# Benchmark results: smoke

> **DEV-HOST BASELINE - not RK3566 numbers**

- Host: Intel(R) Xeon(R) Processor @ 2.10GHz (x86_64, 4 cores, 15.71 GiB RAM), Ubuntu 24.04.5 LTS, kernel 6.18.44-fc-v242
- Date: 2026-11-06T09:19:34+00:00 · repo commit `0b3a6713a1`
- Network isolation: unshare -rn: no network inside the namespace
- Pinned CPUs: `0-3` · warm-up utterances per run: 1

WER/CER are corpus-level on normalised text (see `bench/metrics.py`); raw = only whitespace normalised. RTF = inference time / audio duration, model load excluded. Latency p90 = end of audio → final text (offline engines: whole-utterance processing time; streaming engines: time after the last chunk was fed). Peak RAM = max RSS of the engine process.

| Engine | Model | Lang | Data | Mode | Thr | N | WER | CER | WER raw | RTF mean | RTF p90 | Latency p90 (s) | Load (s) | Peak RAM (MB) | Model (MB) | CPU % | Offline |
|---|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| whisper_cpp | whisper-tiny | fr | fleurs | offline | 4 | 20 | 38.6% | 14.8% | 42.8% | 0.106 | 0.136 | 1.37 | 0.08 | 176 | 78 | 85.3% | yes |
| whisper_cpp | whisper-tiny | en | fleurs | offline | 4 | 20 | 13.8% | 6.4% | 20.8% | 0.077 | 0.100 | 0.81 | 0.09 | 176 | 78 | 83.5% | yes |
| whisper_cpp | whisper-tiny-q5_1 | fr | fleurs | offline | 4 | 20 | 38.6% | 14.8% | 43.4% | 0.132 | 0.169 | 1.60 | 0.05 | 133 | 32 | 89.4% | yes |
| whisper_cpp | whisper-tiny-q5_1 | en | fleurs | offline | 4 | 20 | 13.5% | 6.5% | 22.6% | 0.102 | 0.127 | 1.03 | 0.05 | 132 | 32 | 88.1% | yes |
| whisper_cpp | whisper-tiny-q8_0 | fr | fleurs | offline | 4 | 20 | 38.8% | 15.3% | 42.2% | 0.096 | 0.118 | 1.26 | 0.06 | 146 | 44 | 86.7% | yes |
| whisper_cpp | whisper-tiny-q8_0 | en | fleurs | offline | 4 | 20 | 14.9% | 6.9% | 23.1% | 0.072 | 0.093 | 0.76 | 0.06 | 145 | 44 | 85.8% | yes |
| whisper_cpp | whisper-base | fr | fleurs | offline | 4 | 20 | 24.5% | 9.0% | 31.5% | 0.210 | 0.277 | 2.55 | 0.13 | 283 | 148 | 86.8% | yes |
| whisper_cpp | whisper-base | en | fleurs | offline | 4 | 20 | 8.8% | 4.5% | 15.2% | 0.166 | 0.219 | 1.67 | 0.14 | 282 | 148 | 84.6% | yes |
| whisper_cpp | whisper-base-q5_1 | fr | fleurs | offline | 4 | 20 | 25.7% | 9.2% | 32.9% | 0.241 | 0.311 | 2.79 | 0.07 | 200 | 60 | 91.8% | yes |
| whisper_cpp | whisper-base-q5_1 | en | fleurs | offline | 4 | 20 | 8.1% | 4.3% | 14.8% | 0.201 | 0.264 | 1.94 | 0.07 | 199 | 60 | 91.1% | yes |
| whisper_cpp | whisper-base-q8_0 | fr | fleurs | offline | 4 | 20 | 24.7% | 9.0% | 31.9% | 0.169 | 0.218 | 2.14 | 0.08 | 228 | 82 | 89.7% | yes |
| whisper_cpp | whisper-base-q8_0 | en | fleurs | offline | 4 | 20 | 8.8% | 4.6% | 15.9% | 0.131 | 0.172 | 1.35 | 0.08 | 228 | 82 | 88.4% | yes |
| whisper_cpp | whisper-small | fr | fleurs | offline | 4 | 20 | 12.0% | 4.0% | 19.3% | 0.633 | 0.782 | 7.54 | 0.36 | 746 | 488 | 85.2% | yes |
| whisper_cpp | whisper-small | en | fleurs | offline | 4 | 20 | 6.1% | 3.3% | 12.9% | 0.516 | 0.692 | 5.05 | 0.37 | 746 | 488 | 83.0% | yes |
| vosk | vosk-small-fr-0.22 | fr | fleurs | stream | 4 | 20 | 23.8% | 9.4% | 38.7% | 0.342 | 0.522 | 0.05 | 0.41 | 271 | 68 | 24.8% | yes |
| vosk | vosk-small-en-us-0.15 | en | fleurs | stream | 4 | 20 | 24.8% | 13.6% | 45.0% | 0.205 | 0.269 | 0.05 | 0.41 | 241 | 71 | 24.9% | yes |
| sherpa_onnx | sherpa-zipformer-fr-kroko-2025-08-06 | fr | fleurs | stream | 4 | 20 | 11.8% | 4.9% | 23.5% | 0.058 | 0.069 | 0.08 | 3.25 | 203 | 71 | 99.1% | yes |
| sherpa_onnx | sherpa-zipformer-en-kroko-2025-08-06 | en | fleurs | stream | 4 | 20 | 16.5% | 11.1% | 27.9% | 0.059 | 0.067 | 0.08 | 2.89 | 204 | 71 | 99.1% | yes |
| moonshine | moonshine-tiny-en | en | fleurs | offline | 4 | 20 | 13.8% | 7.5% | 21.0% | 0.027 | 0.035 | 0.30 | 0.85 | 414 | 113 | 99.1% | yes |
| moonshine | moonshine-base-en | en | fleurs | offline | 4 | 20 | 10.6% | 5.7% | 17.3% | 0.042 | 0.050 | 0.49 | 1.51 | 692 | 251 | 98.7% | yes |
| moonshine | moonshine-tiny-fr | fr | fleurs | offline | 4 | 20 | 66.9% | 31.9% | 69.3% | 0.034 | 0.040 | 0.58 | 0.92 | 428 | 113 | 99.1% | yes |

Power: not measured automatically. Use `--power-prompt` with a USB power meter or `python -m bench.power` to add readings.
