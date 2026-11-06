"""Common engine interface.

Every adapter implements:
    load(model_dir, lang, threads, **options)   -- load the model (timed separately)
    transcribe(wav_path) -> str                  -- whole-utterance recognition
and, if `streaming = True`:
    transcribe_stream(wav_path, chunk_s, realtime) -> (text, final_latency_s)

Input is always 16 kHz mono 16-bit WAV (prepared by bench.datasets).
`info()` returns engine/library versions and the exact decoding settings used,
which run.py stores with every result.
"""
import wave

import numpy as np

SAMPLE_RATE = 16000


def read_wav(path):
    """Return int16 samples of a 16 kHz mono 16-bit WAV (raises otherwise)."""
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"{path}: expected 16 kHz mono 16-bit WAV, got "
                             f"{w.getframerate()} Hz, {w.getnchannels()} ch, {8 * w.getsampwidth()} bit")
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def read_wav_float(path):
    return read_wav(path).astype(np.float32) / 32768.0


class Engine:
    name = "base"
    streaming = False

    def load(self, model_dir, lang, threads, **options):
        raise NotImplementedError

    def transcribe(self, wav_path):
        raise NotImplementedError

    def transcribe_stream(self, wav_path, chunk_s=0.1, realtime=False):
        raise NotImplementedError(f"{self.name} has no streaming mode")

    def info(self):
        return {}

    # whisper.cpp runs an external binary per utterance; it overrides this so the
    # worker can account its CPU time and memory as child-process usage.
    uses_child_process = False
