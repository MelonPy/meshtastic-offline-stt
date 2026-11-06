"""Vosk (Kaldi) via the vosk Python package. Streaming by design.

Vosk decodes on one thread per recognizer; the `threads` setting is recorded
but has no effect on a single stream.
"""
import json
import time
from pathlib import Path

from .base import Engine, SAMPLE_RATE, read_wav


class Vosk(Engine):
    name = "vosk"
    streaming = True

    def load(self, model_dir, lang, threads, **_):
        import vosk
        vosk.SetLogLevel(-1)
        dirs = [p for p in Path(model_dir).iterdir() if p.is_dir() and (p / "conf").exists()]
        if len(dirs) != 1:
            raise FileNotFoundError(f"expected one unpacked Vosk model in {model_dir}, found {dirs}")
        self.model_path = dirs[0]
        self.model = vosk.Model(str(self.model_path))
        self.threads = threads

    def _recognizer(self):
        import vosk
        return vosk.KaldiRecognizer(self.model, SAMPLE_RATE)

    @staticmethod
    def _join(parts):
        return " ".join(p for p in parts if p)

    def transcribe(self, wav_path):
        text, _ = self.transcribe_stream(wav_path, chunk_s=1.0)
        return text

    def transcribe_stream(self, wav_path, chunk_s=0.1, realtime=False):
        pcm = read_wav(wav_path)
        rec = self._recognizer()
        step = int(chunk_s * SAMPLE_RATE)
        parts = []
        start = time.perf_counter()
        for i in range(0, len(pcm), step):
            if realtime:  # pace input like a live microphone
                target = start + (i + step) / SAMPLE_RATE
                time.sleep(max(0.0, target - time.perf_counter()))
            if rec.AcceptWaveform(pcm[i:i + step].tobytes()):
                parts.append(json.loads(rec.Result()).get("text", ""))
        t_end = time.perf_counter()  # all audio has been fed
        parts.append(json.loads(rec.FinalResult()).get("text", ""))
        latency = time.perf_counter() - t_end
        return self._join(parts), latency

    def info(self):
        import importlib.metadata as md
        return dict(engine="vosk", version=md.version("vosk"), model_dir=self.model_path.name,
                    decoding=dict(threads_effective=1))
