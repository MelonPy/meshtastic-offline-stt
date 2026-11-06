"""Engine registry. Imports are lazy so a missing engine does not break the others."""
import importlib

ENGINES = {
    "whisper_cpp": ("bench.engines.whisper_cpp", "WhisperCpp"),
    "vosk": ("bench.engines.vosk_engine", "Vosk"),
    "sherpa_onnx": ("bench.engines.sherpa_onnx_engine", "SherpaOnnx"),
    "moonshine": ("bench.engines.moonshine", "Moonshine"),
}


def get_engine(name):
    mod, cls = ENGINES[name]
    return getattr(importlib.import_module(mod), cls)()
