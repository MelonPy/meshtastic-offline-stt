"""Record the mesh-message prompts as 16 kHz mono 16-bit WAV files.

    python -m bench.datasets.record --lang fr [--only fr01 fr02] [--device N]

Press Enter to start, speak, press Enter to stop. Then: Enter = keep,
r = redo, s = skip, q = quit. Files: data/mesh_messages/<lang>/<id>.wav
"""
import argparse
import queue
import sys
import threading
import wave

from .prompts import MESH, load_prompts

RATE = 16000


def record_until_enter(sd, device):
    q = queue.Queue()

    def cb(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))

    stop = threading.Event()
    with sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", device=device, callback=cb):
        threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()
        chunks = []
        while not stop.is_set():
            try:
                chunks.append(q.get(timeout=0.1))
            except queue.Empty:
                pass
        while not q.empty():
            chunks.append(q.get())
    return b"".join(chunks)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["fr", "en"], required=False)
    ap.add_argument("--only", nargs="*", help="prompt ids to record")
    ap.add_argument("--device", default=None, help="input device index or name")
    ap.add_argument("--overwrite", action="store_true", help="re-record existing files")
    ap.add_argument("--list-devices", action="store_true")
    a = ap.parse_args(argv)
    try:
        import sounddevice as sd
    except OSError as e:  # PortAudio missing
        sys.exit(f"sounddevice could not load PortAudio ({e}). Install libportaudio2.")
    if a.list_devices:
        print(sd.query_devices())
        return
    if not a.lang:
        ap.error("--lang is required")
    device = int(a.device) if a.device and a.device.isdigit() else a.device
    out_dir = MESH / a.lang
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts = [p for p in load_prompts(a.lang) if not a.only or p[0] in a.only]
    for pid, text in prompts:
        path = out_dir / f"{pid}.wav"
        if path.exists() and not a.overwrite:
            print(f"[{pid}] exists, skipping (use --overwrite)")
            continue
        while True:
            print(f"\n[{pid}] {text}")
            cmd = input("Enter = start, s = skip, q = quit > ").strip().lower()
            if cmd == "q":
                return
            if cmd == "s":
                break
            print("Recording... press Enter to stop.")
            pcm = record_until_enter(sd, device)
            secs = len(pcm) / 2 / RATE
            cmd = input(f"{secs:.1f} s recorded. Enter = keep, r = redo, s = skip > ").strip().lower()
            if cmd == "r":
                continue
            if cmd != "s":
                with wave.open(str(path), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(RATE)
                    w.writeframes(pcm)
                print(f"saved {path}")
            break


if __name__ == "__main__":
    sys.exit(main())
