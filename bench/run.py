"""Benchmark runner.

    python -m bench.run --config configs/smoke.yaml [--limit N] [--threads 1 2 4]
                        [--only whisper-tiny vosk] [--power-prompt] [--allow-network]

For every (run × model × language × thread count) in the config it starts
`bench.worker` in a fresh process, pinned with `taskset -c <cpus>` and with the
network removed (`unshare -rn`, plus HF_HUB_OFFLINE=1). It writes

    results/<host>_<date>/results.json   everything, incl. host metadata
    results/<host>_<date>/summary.csv
    results/<host>_<date>/summary.md
    results/<host>_<date>/raw/           per-utterance JSONL + logs (gitignored)
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import yaml

from . import hostinfo
from .datasets.common import read_manifest
from .metrics import summarise_utterances

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "configs" / "models.lock.json"
MODELS = ROOT / "models"
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def dir_size(path):
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def verify_model(entry):
    """Re-hash the model files on disk against the lock. Raises on mismatch."""
    mdir = MODELS / entry["id"]
    files = []
    for f in entry["files"]:
        p = mdir / f["path"]
        if not p.exists():
            raise FileNotFoundError(f"{p} missing: run scripts/fetch_models.sh {entry['id']}")
        got = sha256(p)
        if got != f["sha256"]:
            raise RuntimeError(f"SHA256 mismatch for {p}: expected {f['sha256']}, got {got}")
        files.append(dict(path=f["path"], sha256=got, size=f["size"], sha256_source=f["sha256_source"]))
    if entry.get("unpack") == "zip":  # the model is the unpacked directory, not the archive
        unpacked = [p for p in mdir.iterdir() if p.is_dir()]
        size = sum(dir_size(p) for p in unpacked)
        check = subprocess.run(["sha256sum", "--quiet", "-c", ".unpacked.sha256"], cwd=mdir,
                               capture_output=True, text=True)
        if check.returncode != 0:
            raise RuntimeError(f"unpacked files of {entry['id']} changed: {check.stdout}{check.stderr}")
    else:
        size = sum(f["size"] for f in entry["files"])
    return dict(id=entry["id"], source=entry["source"], revision=entry["revision"],
                licence=entry["licence"], size_on_disk_bytes=size, files=files)


def check_network_isolation():
    """Make sure `unshare -rn` works and really has no network."""
    probe = [sys.executable, "-c",
             "import socket,sys\n"
             "try:\n socket.create_connection(('1.1.1.1',443),timeout=3)\nexcept OSError:\n sys.exit(0)\n"
             "sys.exit(3)"]
    try:
        r = subprocess.run(["unshare", "-rn", *probe], capture_output=True, text=True)
    except FileNotFoundError:
        return False, "unshare not found (util-linux)"
    if r.returncode == 0:
        return True, "unshare -rn: no network inside the namespace"
    if r.returncode == 3:
        return False, "network still reachable inside unshare -rn"
    return False, f"unshare -rn failed: {r.stderr.strip()}"


def strace_network_check(cmd, env, log_path):
    """Run cmd under strace; catches network use by native code too.

    Returns (attempts, sockets): attempts are connect/sendto/sendmsg calls to an
    IPv4/IPv6 address (a real attempt to reach the network); sockets are IPv4/IPv6
    socket() creations without any connect, e.g. urllib3's IPv6-support probe at
    import time, kept for information only. None if strace is not installed.
    """
    if not shutil.which("strace"):
        return None
    trace = log_path.with_suffix(".strace")
    subprocess.run(["strace", "-f", "-qq", "--seccomp-bpf", "-e", "trace=socket,connect,sendto,sendmsg",
                    "-o", str(trace), *cmd], env=env, capture_output=True, text=True)
    attempts, sockets = [], []
    for line in trace.read_text(errors="replace").splitlines():
        if not re.search(r"\b[AP]F_INET6?\b", line):
            continue
        target = attempts if re.search(r"\b(connect|sendto|sendmsg)\(", line) else sockets
        target.append(re.sub(r"^\d+\s+", "", line.strip())[:200])
    return dict(attempts=attempts, sockets_created=sockets)


def expand_jobs(cfg, lock, args):
    by_id = {m["id"]: m for m in lock["models"]}
    datasets = cfg["datasets"]
    threads = args.threads or cfg.get("threads", [4])
    jobs = []
    for run in cfg["runs"]:
        for mid in run["models"]:
            if mid not in by_id:
                raise SystemExit(f"model {mid} is not in {LOCK}")
            m = by_id[mid]
            for ds in datasets:
                if ds["lang"] not in m["langs"]:
                    continue
                for t in threads:
                    job = dict(engine=run["engine"], model=mid, lang=ds["lang"], dataset=ds["name"],
                               manifest=str(ROOT / ds["manifest"]), threads=t,
                               mode=run.get("mode", "offline"), chunk_s=run.get("chunk_s", 0.1),
                               realtime=run.get("realtime", False), options=run.get("options", {}),
                               warmup=cfg.get("warmup", 1))
                    tag = f"{run['engine']} {mid} {job['mode']}"
                    if args.only and not any(o in tag for o in args.only):
                        continue
                    jobs.append(job)
    return jobs


def fmt(x, nd=3):
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def write_reports(out_dir, doc):
    rows = []
    for r in doc["runs"]:
        s = r.get("summary") or {}
        rows.append(dict(
            engine=r["engine"], model=r["model"], lang=r["lang"], dataset=r["dataset"], mode=r["mode"],
            threads=r["threads"], n=s.get("n_utterances"), errors=s.get("n_errors"),
            wer=s.get("wer"), cer=s.get("cer"), wer_raw=s.get("wer_raw"), cer_raw=s.get("cer_raw"),
            rtf_mean=s.get("rtf_mean"), rtf_p90=s.get("rtf_p90"),
            latency_p90_s=s.get("latency_p90_s"), stream_latency_p90_s=s.get("stream_latency_p90_s"),
            load_s=r.get("load_s"), peak_rss_mb=r.get("peak_rss_mb"),
            model_mb=r["model_info"]["size_on_disk_bytes"] / 1e6 if r.get("model_info") else None,
            cpu_util_mean=s.get("cpu_util_mean"), power_w=r.get("power", {}).get("active_w"),
            offline_ok=r.get("offline", {}).get("ok"), status=r["status"],
        ))
    with open(out_dir / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["engine"])
        w.writeheader()
        w.writerows(rows)

    h = doc["host"]
    lines = [
        f"# Benchmark results: {doc['config_name']}",
        "",
        f"> **{h['label']}**",
        "",
        f"- Host: {h['cpu_model']} ({h['arch']}, {h['cores']} cores, {h['ram_gib']} GiB RAM), "
        f"{h['os']}, kernel {h['kernel']}" + (f", board: {h['board']}" if h.get("board") else ""),
        f"- Date: {doc['started']} · repo commit `{(h['repo']['commit'] or '?')[:10]}`"
        + (" (dirty)" if h["repo"]["dirty"] else ""),
        f"- Network isolation: {doc['network_isolation']['detail']}",
        f"- Pinned CPUs: `{doc['cpus']}` · warm-up utterances per run: {doc['warmup']}",
        "",
        "WER/CER are corpus-level on normalised text (see `bench/metrics.py`); raw = only whitespace "
        "normalised. RTF = inference time / audio duration, model load excluded. "
        "Latency p90 = end of audio → final text (offline engines: whole-utterance processing time; "
        "streaming engines: time after the last chunk was fed). Peak RAM = max RSS of the engine process.",
        "",
        "| Engine | Model | Lang | Mode | Thr | N | WER | CER | WER raw | RTF mean | RTF p90 | Latency p90 (s) | Load (s) | Peak RAM (MB) | Model (MB) | CPU % | Offline |",
        "|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|",
    ]
    for r in rows:
        lat = r["stream_latency_p90_s"] if r["mode"] == "stream" else r["latency_p90_s"]
        pct = lambda x: "–" if x is None else f"{100 * x:.1f}%"
        lines.append("| " + " | ".join([
            r["engine"], r["model"], r["lang"], r["mode"], str(r["threads"]), fmt(r["n"]),
            pct(r["wer"]), pct(r["cer"]), pct(r["wer_raw"]), fmt(r["rtf_mean"]), fmt(r["rtf_p90"]),
            fmt(lat, 2), fmt(r["load_s"], 2), fmt(r["peak_rss_mb"], 0), fmt(r["model_mb"], 0),
            pct(r["cpu_util_mean"]), {True: "yes", False: "**NO**", None: "–"}[r["offline_ok"]],
        ]) + " |" + ("" if r["status"] == "ok" else f" ⚠ {r['status']}"))
    lines += ["", "Power: not measured automatically. Use `--power-prompt` with a USB power meter "
              "or `python -m bench.power` to add readings.", ""]
    (out_dir / "summary.md").write_text("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--limit", type=int, help="override: first N utterances per dataset")
    ap.add_argument("--threads", type=int, nargs="+", help="override thread counts")
    ap.add_argument("--only", nargs="+", help="only runs whose 'engine model mode' contains one of these")
    ap.add_argument("--out", type=Path, help="output directory (default results/<host>_<date>)")
    ap.add_argument("--allow-network", action="store_true",
                    help="run without network isolation (results are then marked offline_ok=false)")
    ap.add_argument("--no-strace", action="store_true", help="skip the strace network-attempt check")
    ap.add_argument("--power-prompt", action="store_true",
                    help="after each run, ask for a manual power meter reading (W)")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(args.config.read_text())
    lock = json.loads(LOCK.read_text())
    limit = args.limit if args.limit is not None else cfg.get("limit")
    cpus = str(cfg.get("cpus", "0-3"))
    jobs = expand_jobs(cfg, lock, args)
    if not jobs:
        raise SystemExit("no jobs selected")

    iso_ok, iso_detail = check_network_isolation()
    if not iso_ok and not args.allow_network:
        raise SystemExit(f"Network isolation unavailable: {iso_detail}\n"
                         "Fix it (e.g. sudo sysctl kernel.unprivileged_userns_clone=1) "
                         "or pass --allow-network to run without the offline guarantee.")
    use_unshare = iso_ok and not args.allow_network

    host = hostinfo.collect()
    started = dt.datetime.now().astimezone()
    out_dir = args.out or ROOT / "results" / f"{socket.gethostname()}_{started:%Y-%m-%d}"
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"{host['label']}\n{len(jobs)} runs -> {out_dir}")

    doc = dict(config_name=args.config.stem, config_path=str(args.config), config=cfg,
               cli=dict(limit=limit, threads=args.threads, only=args.only,
                        allow_network=args.allow_network),
               started=started.isoformat(timespec="seconds"), cpus=cpus, warmup=cfg.get("warmup", 1),
               host=host, network_isolation=dict(enabled=use_unshare, detail=iso_detail,
                                                  env=OFFLINE_ENV),
               runs=[])
    model_cache, strace_done = {}, {}
    by_id = {m["id"]: m for m in lock["models"]}

    for i, job in enumerate(jobs, 1):
        name = f"{job['engine']}__{job['model']}__{job['lang']}__{job['mode']}__t{job['threads']}"
        print(f"[{i}/{len(jobs)}] {name}", flush=True)
        rec = dict(engine=job["engine"], model=job["model"], lang=job["lang"], dataset=job["dataset"],
                   mode=job["mode"], threads=job["threads"], options=job["options"],
                   chunk_s=job["chunk_s"] if job["mode"] == "stream" else None,
                   realtime=job["realtime"] if job["mode"] == "stream" else None,
                   power=dict(idle_w=None, active_w=None, meter=None, note="manual reading; not measured"))
        try:
            if job["model"] not in model_cache:
                model_cache[job["model"]] = verify_model(by_id[job["model"]])
            rec["model_info"] = model_cache[job["model"]]
            manifest = Path(job["manifest"])
            if not manifest.exists():
                raise FileNotFoundError(f"{manifest} missing: prepare the dataset first (see README)")
            n_utts = len(read_manifest(manifest, limit))
            wjob = dict(job, model_dir=str(MODELS / job["model"]), limit=limit,
                        out=str(raw_dir / f"{name}.jsonl"))
            job_path = raw_dir / f"{name}.job.json"
            job_path.write_text(json.dumps(wjob, indent=2))
            env = dict(os.environ, **OFFLINE_ENV, OMP_NUM_THREADS=str(job["threads"]),
                       PYTHONPATH=str(ROOT))
            prefix = ["taskset", "-c", cpus] + (["unshare", "-rn"] if use_unshare else [])
            cmd = prefix + [sys.executable, "-m", "bench.worker", str(job_path)]
            rec["command"] = cmd

            # Network-attempt check on 1 utterance under strace (also sees native code).
            key = (job["engine"], job["model"], job["mode"])
            if not args.no_strace and key not in strace_done:
                sjob = dict(wjob, limit=1, warmup=0, out=str(raw_dir / f"{name}.strace.jsonl"))
                sjob_path = raw_dir / f"{name}.strace.job.json"
                sjob_path.write_text(json.dumps(sjob))
                strace_done[key] = strace_network_check(
                    prefix + [sys.executable, "-m", "bench.worker", str(sjob_path)], env,
                    raw_dir / f"{name}.log")
            native_hits = strace_done.get(key)

            log = open(raw_dir / f"{name}.log", "w")
            p = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
            log.close()
            if p.returncode != 0:
                tail = (raw_dir / f"{name}.log").read_text()[-1500:]
                raise RuntimeError(f"worker exited with {p.returncode}:\n{tail}")
            lines = [json.loads(x) for x in open(wjob["out"], encoding="utf-8")]
            utts = [x for x in lines if not x.get("_summary")]
            wsum = next(x for x in lines if x.get("_summary"))
            rec.update(load_s=wsum["load_s"], peak_rss_mb=wsum["peak_rss_mb"],
                       peak_rss_scope=wsum["peak_rss_scope"], baseline_rss_mb=wsum["baseline_rss_mb"],
                       rss_after_load_mb=wsum["rss_after_load_mb"], cpus_allowed=wsum["cpus_allowed"],
                       engine_info=wsum["engine_info"], summary=summarise_utterances(utts),
                       utterances=[{k: u.get(k) for k in ("utt_id", "duration", "hypothesis", "proc_s",
                                                         "rtf", "cpu_util", "stream_latency_s", "error")}
                                   for u in utts])
            attempts_py = wsum["net_attempts"]
            rec["offline"] = dict(
                network_namespace=use_unshare, python_net_attempts=attempts_py,
                strace=native_hits,
                ok=use_unshare and not attempts_py and not (native_hits or {}).get("attempts"))
            if attempts_py or (native_hits or {}).get("attempts"):
                print(f"  WARNING: network access attempted: {attempts_py or native_hits['attempts']}")
            rec["status"] = "ok" if rec["summary"]["n_errors"] == 0 else f"{rec['summary']['n_errors']} utterance errors"
            if n_utts != rec["summary"]["n_utterances"] + rec["summary"]["n_errors"]:
                rec["status"] = "incomplete"
            s = rec["summary"]
            print(f"  WER {100 * (s['wer'] or 0):.1f}%  RTF {s['rtf_mean']:.3f}  "
                  f"peak RSS {rec['peak_rss_mb']:.0f} MB  load {rec['load_s']:.2f}s", flush=True)
        except Exception as e:
            rec["status"] = f"error: {e}"
            print(f"  ERROR: {e}", flush=True)
        if args.power_prompt and rec["status"] == "ok":
            v = input("  power meter reading during this run (W, blank to skip): ").strip()
            if v:
                rec["power"].update(active_w=float(v), meter="manual (--power-prompt)")
        doc["runs"].append(rec)
        doc["finished"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        (out_dir / "results.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        write_reports(out_dir, doc)

    print(f"\nwrote {out_dir / 'results.json'}\n      {out_dir / 'summary.md'}")
    return 0 if all(r["status"] == "ok" for r in doc["runs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
