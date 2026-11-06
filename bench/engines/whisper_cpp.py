"""whisper.cpp via the whisper-cli binary (built by scripts/setup_host.sh).

whisper-cli is started once per utterance, so it reloads the model each time.
The processing time used for RTF is whisper.cpp's own "total time" minus its
"load time" (both printed by whisper_print_timings); the load time is reported
separately. The wall-clock time including process start and load is kept too.
"""
import re
import subprocess
from pathlib import Path

from .base import Engine

ROOT = Path(__file__).resolve().parents[2]
WHISPER_CLI = ROOT / "third_party" / "whisper.cpp" / "build" / "bin" / "whisper-cli"
TIMING = re.compile(r"whisper_print_timings:\s+(\w+) time =\s+([\d.]+) ms")


class WhisperCpp(Engine):
    name = "whisper_cpp"
    uses_child_process = True

    def load(self, model_dir, lang, threads, beam_size=5, best_of=5, flash_attn=True,
             no_fallback=False, binary=None, **_):
        self.bin = Path(binary) if binary else WHISPER_CLI
        if not self.bin.exists():
            raise FileNotFoundError(f"{self.bin} not found: run scripts/setup_host.sh")
        bins = sorted(Path(model_dir).glob("ggml-*.bin"))
        if len(bins) != 1:
            raise FileNotFoundError(f"expected one ggml-*.bin in {model_dir}, found {bins}")
        self.model = bins[0]
        self.args = ["-m", str(self.model), "-l", lang, "-t", str(threads), "-nt",
                     "-bs", str(beam_size), "-bo", str(best_of),
                     "-fa" if flash_attn else "-nfa"]
        if no_fallback:
            self.args.append("-nf")
        self.settings = dict(beam_size=beam_size, best_of=best_of, flash_attn=flash_attn,
                             no_fallback=no_fallback, threads=threads, lang=lang)
        self.last_timings = {}

    def transcribe(self, wav_path):
        p = subprocess.run([str(self.bin), *self.args, "-f", str(wav_path)],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if p.returncode != 0:
            raise RuntimeError(f"whisper-cli failed ({p.returncode}): {p.stderr[-2000:]}")
        t = {k: float(v) / 1000 for k, v in TIMING.findall(p.stderr)}
        self.last_timings = t
        return " ".join(line.strip() for line in p.stdout.splitlines() if line.strip())

    def processing_time(self):
        """Seconds of inference for the last call, excluding model load."""
        t = self.last_timings
        return t["total"] - t.get("load", 0.0) if "total" in t else None

    def info(self):
        try:
            commit = subprocess.run(["git", "-C", str(WHISPER_CLI.parents[3]), "rev-parse", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
            tag = subprocess.run(["git", "-C", str(WHISPER_CLI.parents[3]), "describe", "--tags"],
                                 capture_output=True, text=True).stdout.strip()
        except OSError:
            commit = tag = None
        return dict(engine="whisper.cpp", version=tag, commit=commit, binary=str(self.bin),
                    cli_args=self.args, decoding=self.settings)
