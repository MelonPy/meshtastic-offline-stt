"""Host metadata embedded in every result file."""
import importlib.metadata as md
import os
import platform
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["vosk", "sherpa-onnx", "onnxruntime", "tokenizers", "numpy", "jiwer", "psutil"]


def _read(path):
    try:
        return Path(path).read_text(errors="replace").strip("\x00\n ")
    except OSError:
        return None


def cpu_model():
    model, parts = None, set()
    for line in (_read("/proc/cpuinfo") or "").splitlines():
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if k in ("model name", "Model") and not model:
            model = v
        if k == "CPU part":
            parts.add(v)
    if not model and parts:  # ARM: map the common part numbers
        names = {"0xd05": "Cortex-A55", "0xd03": "Cortex-A53", "0xd08": "Cortex-A72", "0xd0b": "Cortex-A76"}
        model = " + ".join(sorted(names.get(p, p) for p in parts))
    return model or platform.processor() or None


def os_release():
    info = {}
    for line in (_read("/etc/os-release") or "").splitlines():
        k, _, v = line.partition("=")
        info[k] = v.strip('"')
    return info.get("PRETTY_NAME")


def git_info():
    def g(*a):
        r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    return dict(commit=g("rev-parse", "HEAD"), branch=g("rev-parse", "--abbrev-ref", "HEAD"),
                dirty=bool(g("status", "--porcelain", "--untracked-files=no")))


def collect():
    board = _read("/proc/device-tree/model")
    mem = None
    for line in (_read("/proc/meminfo") or "").splitlines():
        if line.startswith("MemTotal:"):
            mem = int(line.split()[1]) / 2**20
    is_target = bool(board and "ZERO 3" in board.upper().replace("ZERO3", "ZERO 3"))
    try:
        ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split("\n")[0]
    except OSError:
        ffmpeg = None
    pkgs = {}
    for p in PACKAGES:
        try:
            pkgs[p] = md.version(p)
        except md.PackageNotFoundError:
            pkgs[p] = None
    gov = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    fmax = _read("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
    return dict(
        hostname=socket.gethostname(),
        label=("RK3566 target (Radxa ZERO 3W)" if is_target
               else "DEV-HOST BASELINE - not RK3566 numbers"),
        is_target_board=is_target,
        board=board, cpu_model=cpu_model(), arch=platform.machine(), cores=os.cpu_count(),
        ram_gib=round(mem, 2) if mem else None, os=os_release(), kernel=platform.release(),
        cpu_governor=gov, cpu_max_khz=int(fmax) if fmax and fmax.isdigit() else None,
        python=platform.python_version(), packages=pkgs, ffmpeg=ffmpeg, repo=git_info(),
    )
