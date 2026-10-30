"""EXORCIST CLI.

    python code/main.py                       # audit dataset/deletion_requests.csv -> ./output.csv
    python code/main.py --input dataset/sample_deletion_requests.csv --output /tmp/sample.csv
    python code/main.py --explain case_18 --input dataset/sample_deletion_requests.csv
    python code/main.py --coverage            # evidence coverage report
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from exorcist.auditor import Auditor, read_requests  # noqa: E402
from exorcist.config import DATASET_DIR, OUTPUT_CSV  # noqa: E402
from exorcist.planner import serialize  # noqa: E402


def write_output(rows, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "deletion_status", "steps_json"])
        for r in rows:
            w.writerow([r["case_id"], r["deletion_status"], serialize(r["steps"])])


def explain(row) -> str:
    lines = [f"{row['case_id']}: {row['deletion_status']}  subject={row['trace'].get('uid')}"]
    conf = row["trace"].get("confidence", {})
    for it in row["trace"].get("items", []):
        st = it.state
        c = conf.get((st.system_id, st.resource_id), (0, 0, 0))
        lines.append(f"  {st.system_id}/{st.resource_id}: confidence={c[0]:.3f} "
                     f"(P(state)={c[1]:.3f} x P(link)={c[2]:.3f}) treatment={it.treatment} "
                     f"exists={st.exists} status={st.status} violation={it.violation} "
                     f"proof={it.evidence} linked_by={sorted(it.reasons)} workflow={st.workflow_actions}")
        for o in st.observations[-4:]:
            lines.append(f"      {o.observed_at} {o.evidence_id:<14} {o.source_kind:<9} "
                         f"{o.source[:28]:<28} present={o.present} status={o.status}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXORCIST deletion auditor")
    ap.add_argument("--input", type=Path, default=DATASET_DIR / "deletion_requests.csv")
    ap.add_argument("--output", type=Path, default=OUTPUT_CSV)
    ap.add_argument("--explain", metavar="CASE_ID")
    ap.add_argument("--coverage", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    auditor = Auditor()
    if args.coverage:
        print(auditor.store.coverage_report())
        return 0
    rows = auditor.audit(read_requests(args.input))
    if args.explain:
        for r in rows:
            if r["case_id"] == args.explain:
                print(explain(r))
        return 0
    write_output(rows, args.output)
    counts = {}
    for r in rows:
        counts[r["deletion_status"]] = counts.get(r["deletion_status"], 0) + 1
    print(f"wrote {len(rows)} rows to {args.output}  {counts}  "
          f"compile {auditor.compile_seconds:.2f}s  total {time.perf_counter() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
