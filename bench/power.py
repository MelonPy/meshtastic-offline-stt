"""Add manual power meter readings to an existing results.json.

Power is not measured automatically (there is no meter on the dev host, and a
USB power meter is read by eye). Either answer the prompts of
`bench.run --power-prompt`, or add readings afterwards:

    python -m bench.power results/<dir> --idle 1.2 --meter "FNIRSI FNB58"
    python -m bench.power results/<dir> --run whisper-tiny-q8_0 --lang fr --active 2.9

--run matches a substring of the model id; --lang/--threads narrow it further.
summary.csv / summary.md are regenerated.
"""
import argparse
import json
from pathlib import Path

from .run import write_reports


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_dir", type=Path)
    ap.add_argument("--run", help="model id substring (default: all runs)")
    ap.add_argument("--lang")
    ap.add_argument("--threads", type=int)
    ap.add_argument("--idle", type=float, help="idle board power (W)")
    ap.add_argument("--active", type=float, help="power during transcription (W)")
    ap.add_argument("--meter", help="meter model / method")
    a = ap.parse_args(argv)
    path = a.results_dir / "results.json"
    doc = json.loads(path.read_text())
    n = 0
    for r in doc["runs"]:
        if a.run and a.run not in r["model"]:
            continue
        if a.lang and r["lang"] != a.lang or a.threads and r["threads"] != a.threads:
            continue
        p = r.setdefault("power", {})
        if a.idle is not None:
            p["idle_w"] = a.idle
        if a.active is not None:
            p["active_w"] = a.active
        if a.meter:
            p["meter"] = a.meter
        p["note"] = "manual reading"
        n += 1
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    write_reports(a.results_dir, doc)
    print(f"updated {n} run(s) in {path}")


if __name__ == "__main__":
    main()
