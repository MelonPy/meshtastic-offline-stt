# Benchmark results: smoke_peaknorm

> **DEV-HOST BASELINE - not RK3566 numbers**

- Host: Intel(R) Xeon(R) Processor @ 2.10GHz (x86_64, 4 cores, 15.71 GiB RAM), Ubuntu 24.04.5 LTS, kernel 6.18.44-fc-v242
- Date: 2026-11-06T14:19:05+00:00 · repo commit `4297dab4b5`
- Network isolation: unshare -rn: no network inside the namespace
- Pinned CPUs: `0-3` · warm-up utterances per run: 1

WER/CER are corpus-level on normalised text (see `bench/metrics.py`); raw = only whitespace normalised. RTF = inference time / audio duration, model load excluded. Latency p90 = end of audio → final text (offline engines: whole-utterance processing time; streaming engines: time after the last chunk was fed). Peak RAM = max RSS of the engine process.

| Engine | Model | Lang | Data | Mode | Thr | N | WER | CER | WER raw | RTF mean | RTF p90 | Latency p90 (s) | Load (s) | Peak RAM (MB) | Model (MB) | CPU % | Offline |
|---|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|
| whisper_cpp | whisper-tiny | fr | fleurs-peak-3dB | offline | 4 | 20 | 39.9% | 14.9% | 43.6% | 0.116 | 0.142 | 1.66 | 0.08 | 176 | 78 | 86.3% | yes |
| whisper_cpp | whisper-tiny | en | fleurs-peak-3dB | offline | 4 | 20 | 13.3% | 6.4% | 20.3% | 0.107 | 0.148 | 1.15 | 0.11 | 175 | 78 | 83.8% | yes |
| whisper_cpp | whisper-tiny-q5_1 | fr | fleurs-peak-3dB | offline | 4 | 20 | 39.0% | 15.4% | 44.4% | 0.138 | 0.167 | 1.75 | 0.06 | 133 | 32 | 89.9% | yes |
| whisper_cpp | whisper-tiny-q5_1 | en | fleurs-peak-3dB | offline | 4 | 20 | 12.2% | 5.8% | 20.3% | 0.120 | 0.146 | 1.32 | 0.07 | 132 | 32 | 87.4% | yes |
| whisper_cpp | whisper-tiny-q8_0 | fr | fleurs-peak-3dB | offline | 4 | 20 | 36.7% | 14.0% | 41.8% | 0.106 | 0.138 | 1.37 | 0.07 | 145 | 44 | 87.6% | yes |
| whisper_cpp | whisper-tiny-q8_0 | en | fleurs-peak-3dB | offline | 4 | 20 | 13.5% | 6.4% | 20.6% | 0.074 | 0.094 | 0.79 | 0.06 | 145 | 44 | 85.7% | yes |
| whisper_cpp | whisper-base | fr | fleurs-peak-3dB | offline | 4 | 20 | 24.5% | 9.5% | 32.3% | 0.198 | 0.261 | 2.46 | 0.13 | 282 | 148 | 87.8% | yes |
| whisper_cpp | whisper-base | en | fleurs-peak-3dB | offline | 4 | 20 | 9.3% | 5.0% | 15.7% | 0.155 | 0.189 | 1.67 | 0.13 | 282 | 148 | 86.1% | yes |
| whisper_cpp | whisper-base-q5_1 | fr | fleurs-peak-3dB | offline | 4 | 20 | 24.2% | 8.9% | 30.5% | 0.253 | 0.313 | 2.93 | 0.07 | 199 | 60 | 92.1% | yes |
| whisper_cpp | whisper-base-q5_1 | en | fleurs-peak-3dB | offline | 4 | 20 | 9.7% | 6.0% | 16.9% | 0.206 | 0.273 | 2.10 | 0.07 | 199 | 60 | 91.6% | yes |
| whisper_cpp | whisper-base-q8_0 | fr | fleurs-peak-3dB | offline | 4 | 20 | 23.6% | 9.0% | 31.1% | 0.171 | 0.217 | 2.22 | 0.08 | 227 | 82 | 89.9% | yes |
| whisper_cpp | whisper-base-q8_0 | en | fleurs-peak-3dB | offline | 4 | 20 | 8.6% | 4.8% | 15.0% | 0.131 | 0.168 | 1.36 | 0.08 | 227 | 82 | 88.6% | yes |
| whisper_cpp | whisper-small | fr | fleurs-peak-3dB | offline | 4 | 20 | 11.6% | 4.0% | 19.3% | 0.601 | 0.742 | 6.97 | 0.37 | 746 | 488 | 84.0% | yes |
| whisper_cpp | whisper-small | en | fleurs-peak-3dB | offline | 4 | 20 | 5.9% | 3.2% | 12.0% | 0.482 | 0.613 | 4.93 | 0.37 | 745 | 488 | 82.5% | yes |
| vosk | vosk-small-fr-0.22 | fr | fleurs-peak-3dB | stream | 4 | 20 | 24.0% | 9.4% | 38.7% | 0.336 | 0.488 | 0.04 | 0.40 | 252 | 68 | 24.8% | yes |
| vosk | vosk-small-en-us-0.15 | en | fleurs-peak-3dB | stream | 4 | 20 | 21.0% | 10.4% | 41.8% | 0.188 | 0.239 | 0.03 | 0.40 | 229 | 71 | 24.8% | yes |
| sherpa_onnx | sherpa-zipformer-fr-kroko-2025-08-06 | fr | fleurs-peak-3dB | stream | 4 | 20 | 11.8% | 4.9% | 23.5% | 0.058 | 0.063 | 0.08 | 3.11 | 192 | 71 | 98.6% | yes |
| sherpa_onnx | sherpa-zipformer-en-kroko-2025-08-06 | en | fleurs-peak-3dB | stream | 4 | 20 | 13.1% | 7.0% | 23.3% | 0.054 | 0.061 | 0.07 | 2.80 | 193 | 71 | 98.9% | yes |
| moonshine | moonshine-tiny-en | en | fleurs-peak-3dB | offline | 4 | 20 | 11.7% | 6.3% | 19.4% | 0.025 | 0.030 | 0.28 | 1.12 | 402 | 113 | 97.9% | yes |
| moonshine | moonshine-base-en | en | fleurs-peak-3dB | offline | 4 | 20 | 10.2% | 5.4% | 17.1% | 0.040 | 0.049 | 0.47 | 1.67 | 682 | 251 | 98.5% | yes |
| moonshine | moonshine-tiny-fr | fr | fleurs-peak-3dB | offline | 4 | 20 | 65.2% | 30.5% | 67.3% | 0.033 | 0.038 | 0.51 | 1.29 | 412 | 113 | 98.2% | yes |

Power: not measured automatically. Use `--power-prompt` with a USB power meter or `python -m bench.power` to add readings.
