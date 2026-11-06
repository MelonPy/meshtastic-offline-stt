"""Benchmark worker: runs ONE engine/model/lang/threads job in its own process.

Started by bench.run (normally under `taskset` and `unshare -rn`), so that the
memory and CPU figures belong to this engine alone.

    python -m bench.worker JOB.json

JOB.json keys: engine, model_dir, lang, threads, options, mode ("offline" or
"stream"), chunk_s, realtime, manifest, limit, warmup, out (jsonl path).

Measurements:
  - load_s: wall time of engine.load() (model load), excluded from RTF
  - per utterance: proc_s (inference time; for whisper.cpp its own total-load),
    wall_s, RTF = proc_s / duration, CPU utilisation = CPU time / wall time /
    number of CPUs this process may use, and for stream mode the final latency
    (time from the last audio chunk being fed to the final text)
  - peak_rss_mb: kernel high-water mark (getrusage ru_maxrss) of this process,
    or of the whisper-cli child processes for whisper.cpp
  - net_attempts: Python-level socket activity seen by an audit hook
"""
import json
import os
import resource
import sys
import time
import traceback

NET_EVENTS = {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
              "socket.sendto", "urllib.Request", "http.client.connect"}
net_attempts = []


def _audit(event, args):
    if event in NET_EVENTS and len(net_attempts) < 50:
        try:
            desc = repr(args)[:200]
        except Exception:
            desc = "?"
        net_attempts.append(f"{event} {desc}")


def rss_mb():
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
    except OSError:
        return None


def maxrss_mb(who):
    return resource.getrusage(who).ru_maxrss / 1024  # Linux: kilobytes


def cpu_times(child):
    r = resource.getrusage(resource.RUSAGE_CHILDREN if child else resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def main(job_path):
    sys.addaudithook(_audit)
    job = json.load(open(job_path))
    baseline_rss = rss_mb()

    from bench.datasets.common import read_manifest
    from bench.engines import get_engine

    utts = read_manifest(job["manifest"], job.get("limit"))
    out = open(job["out"], "w", encoding="utf-8")
    ncpu = len(os.sched_getaffinity(0))
    engine = get_engine(job["engine"])
    child = engine.uses_child_process
    stream = job.get("mode") == "stream"
    if stream and not engine.streaming:
        raise SystemExit(f"{job['engine']} has no streaming mode")

    t0 = time.perf_counter()
    engine.load(job["model_dir"], job["lang"], job["threads"], **job.get("options", {}))
    load_s = time.perf_counter() - t0
    rss_after_load = rss_mb()

    def run_one(path):
        c0, w0 = cpu_times(child), time.perf_counter()
        lat = None
        if stream:
            text, lat = engine.transcribe_stream(path, job.get("chunk_s", 0.1), job.get("realtime", False))
        else:
            text = engine.transcribe(path)
        wall = time.perf_counter() - w0
        cpu = cpu_times(child) - c0
        proc = engine.processing_time() if hasattr(engine, "processing_time") else None
        return text, (proc if proc is not None else wall), wall, cpu, lat

    load_in_call = []
    for _ in range(job.get("warmup", 1)):
        if utts:
            run_one(utts[0]["path"])  # warm caches / lazy init, not recorded

    for u in utts:
        rec = dict(utt_id=u["utt_id"], duration=u["duration"], reference=u["reference"])
        try:
            text, proc, wall, cpu, lat = run_one(u["path"])
            rec.update(hypothesis=text, proc_s=proc, wall_s=wall, rtf=proc / u["duration"],
                       cpu_s=cpu, cpu_util=(cpu / wall / ncpu) if wall > 0 else None,
                       stream_latency_s=lat, error=None)
            if child and getattr(engine, "last_timings", None):
                load_in_call.append(engine.last_timings.get("load"))
        except Exception as e:  # keep going, but record it
            rec.update(hypothesis="", proc_s=None, error=f"{type(e).__name__}: {e}")
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

    if child and load_in_call:
        vals = [x for x in load_in_call if x is not None]
        load_s = sum(vals) / len(vals) if vals else load_s  # model load inside each whisper-cli call

    summary = dict(
        _summary=True, load_s=load_s, cpus_allowed=ncpu,
        baseline_rss_mb=baseline_rss, rss_after_load_mb=rss_after_load,
        peak_rss_mb=maxrss_mb(resource.RUSAGE_CHILDREN if child else resource.RUSAGE_SELF),
        peak_rss_scope="whisper-cli child process" if child else "worker process (Python + engine)",
        net_attempts=net_attempts, engine_info=engine.info(),
    )
    out.write(json.dumps(summary, ensure_ascii=False) + "\n")
    out.close()


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception:
        traceback.print_exc()
        sys.exit(1)
