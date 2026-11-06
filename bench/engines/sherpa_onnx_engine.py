"""sherpa-onnx streaming transducer (zipformer) via the sherpa_onnx package."""
import time
from pathlib import Path

import numpy as np

from .base import Engine, SAMPLE_RATE, read_wav_float


class SherpaOnnx(Engine):
    name = "sherpa_onnx"
    streaming = True

    def load(self, model_dir, lang, threads, decoding_method="greedy_search",
             tail_padding_s=0.66, **_):
        import sherpa_onnx
        d = Path(model_dir)

        def one(pattern):
            m = sorted(d.glob(pattern))
            if len(m) != 1:
                raise FileNotFoundError(f"expected one {pattern} in {d}, found {m}")
            return str(m[0])

        self.rec = sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=one("encoder*.onnx"), decoder=one("decoder*.onnx"), joiner=one("joiner*.onnx"),
            tokens=one("tokens.txt"), num_threads=threads, sample_rate=SAMPLE_RATE,
            feature_dim=80, decoding_method=decoding_method, provider="cpu")
        self.tail = np.zeros(int(tail_padding_s * SAMPLE_RATE), dtype=np.float32)
        self.settings = dict(decoding_method=decoding_method, threads=threads,
                             tail_padding_s=tail_padding_s)

    def transcribe(self, wav_path):
        text, _ = self.transcribe_stream(wav_path, chunk_s=1.0)
        return text

    def transcribe_stream(self, wav_path, chunk_s=0.1, realtime=False):
        audio = read_wav_float(wav_path)
        s = self.rec.create_stream()
        step = int(chunk_s * SAMPLE_RATE)
        start = time.perf_counter()
        for i in range(0, len(audio), step):
            if realtime:
                target = start + (i + step) / SAMPLE_RATE
                time.sleep(max(0.0, target - time.perf_counter()))
            s.accept_waveform(SAMPLE_RATE, audio[i:i + step])
            while self.rec.is_ready(s):
                self.rec.decode_stream(s)
        t_end = time.perf_counter()  # all audio has been fed
        # Tail padding flushes the encoder's right context; it is part of the latency.
        s.accept_waveform(SAMPLE_RATE, self.tail)
        s.input_finished()
        while self.rec.is_ready(s):
            self.rec.decode_stream(s)
        text = self.rec.get_result(s).strip()
        return text, time.perf_counter() - t_end

    def info(self):
        import importlib.metadata as md
        return dict(engine="sherpa-onnx", version=md.version("sherpa-onnx"),
                    onnxruntime=None, decoding=self.settings)
