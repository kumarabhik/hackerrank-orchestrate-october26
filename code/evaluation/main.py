"""EXORCIST evaluation workflow.

    python code/evaluation/main.py                 # score samples + invariants on ./output.csv
    python code/evaluation/main.py --write-report  # also refresh the metrics block in
                                                   # code/evaluation/evaluation_report.md

Metrics (design_doc §10): case status accuracy + confusion matrix; step-level
precision/recall/F1 over (phase, system_id, resource_id, operation, state); field
accuracy over aligned steps (evidence_id reported separately); sequence accuracy
(exact ordered match) and mean normalized Levenshtein similarity; exact row match.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))

from exorcist.auditor import Auditor, case_sort_key, read_requests  # noqa: E402
from exorcist.config import DATASET_DIR, OPERATIONS, OUTPUT_CSV, PHASE_RANK, OPERATION_RANK, STATUSES  # noqa: E402

REPORT = Path(__file__).resolve().parent / "evaluation_report.md"
BEGIN, END = "<!-- METRICS:BEGIN -->", "<!-- METRICS:END -->"
FIELDS = ("phase", "system_id", "resource_id", "operation", "state", "evidence_id")


def tup(s):
    return (s["phase"], s["system_id"], s["resource_id"], s["operation"], s["state"])


def levenshtein(a, b) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def score(pred: dict, gold: dict) -> dict:
    status_ok, confusion = 0, Counter()
    tp = fp = fn = 0
    field_hits, field_total = Counter(), 0
    ev_hit = ev_total = 0
    seq_ok = exact = 0
    lev = []
    per_case = []
    for cid, (gs, gsteps) in sorted(gold.items()):
        ps, psteps = pred.get(cid, ("MISSING", []))
        status_ok += ps == gs
        confusion[(gs, ps)] += 1
        gt, pt = [tup(s) for s in gsteps], [tup(s) for s in psteps]
        gset, pset = Counter(gt), Counter(pt)
        c_tp = sum((gset & pset).values())
        tp += c_tp; fp += sum(pset.values()) - c_tp; fn += sum(gset.values()) - c_tp
        # field accuracy on index-aligned steps
        for g, p in zip(gsteps, psteps):
            field_total += 1
            for f in FIELDS:
                field_hits[f] += g.get(f) == p.get(f)
        field_total += abs(len(gsteps) - len(psteps))
        # evidence accuracy on matched tuples
        pev = {tup(s): s["evidence_id"] for s in psteps}
        for s in gsteps:
            if tup(s) in pev:
                ev_total += 1
                ev_hit += pev[tup(s)] == s["evidence_id"]
        seq_ok += gt == pt
        exact += ps == gs and [dict(s) for s in gsteps] == [dict(s) for s in psteps]
        n = max(len(gt), len(pt)) or 1
        lev.append(1 - levenshtein(gt, pt) / n)
        if ps != gs or gt != pt:
            per_case.append((cid, gs, ps, sorted(set(gt) - set(pt)), sorted(set(pt) - set(gt))))
    n = len(gold)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    return {
        "cases": n, "status_acc": status_ok / n, "confusion": confusion,
        "step_p": prec, "step_r": rec, "step_f1": 2 * prec * rec / (prec + rec) if prec + rec else 0,
        "field_acc": {f: field_hits[f] / field_total for f in FIELDS} if field_total else {},
        "evidence_acc": ev_hit / ev_total if ev_total else 0, "evidence_n": ev_total,
        "seq_acc": seq_ok / n, "lev_sim": sum(lev) / n, "exact": exact / n, "mismatches": per_case,
    }


def load_csv(path: Path) -> dict:
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(fh)}


def invariants(path: Path, requests: list[dict], manifest_time: dict) -> list[str]:
    """Contract checks on a prediction file; returns a list of violations."""
    errs = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = list(reader)
    if header != ["case_id", "deletion_status", "steps_json"]:
        errs.append(f"bad header {header}")
    ids = [r[0] for r in rows]
    want = sorted((q["case_id"] for q in requests), key=case_sort_key)
    if ids != want:
        errs.append(f"case_ids differ from requests or not sorted ({len(ids)} vs {len(want)})")
    audit = {q["case_id"]: q["audit_at"] for q in requests}
    for cid, status, sj in rows:
        if status not in STATUSES:
            errs.append(f"{cid}: bad status {status}")
        try:
            steps = json.loads(sj)
        except json.JSONDecodeError:
            errs.append(f"{cid}: invalid JSON"); continue
        if status == "NOT_APPLICABLE" and steps:
            errs.append(f"{cid}: NOT_APPLICABLE must be []")
        if [s.get("step_no") for s in steps] != list(range(1, len(steps) + 1)):
            errs.append(f"{cid}: step_no not consecutive")
        keys = [(PHASE_RANK[s["phase"]], OPERATION_RANK[s["operation"]], s["system_id"], s["resource_id"]) for s in steps]
        if keys != sorted(keys):
            errs.append(f"{cid}: steps not in canonical order")
        for s in steps:
            if OPERATIONS.get(s["operation"]) != (s["phase"], s["state"]):
                errs.append(f"{cid}: illegal op/phase/state {s['operation']}/{s['phase']}/{s['state']}")
            ev = s["evidence_id"]
            future = status == "INCOMPLETE" and s["phase"] != "FINDING"
            if future and ev:
                errs.append(f"{cid}: future step carries evidence")
            if status == "COMPLETE" and not ev:
                errs.append(f"{cid}: COMPLETE verification without evidence ({s['resource_id']})")
            if ev in manifest_time and manifest_time[ev] > audit[cid]:
                errs.append(f"{cid}: cites {ev} captured after audit_at")
        if status == "COMPLETE" and any(s["phase"] != "VERIFICATION" for s in steps):
            errs.append(f"{cid}: COMPLETE with non-verification steps")
    return errs


def metrics_markdown(m: dict, runtime: float, inv_sample: list, inv_full: list | None) -> str:
    c = m["confusion"]
    labels = list(STATUSES)
    conf = ["| gold \\ pred | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for g in labels:
        conf.append(f"| {g} | " + " | ".join(str(c.get((g, p), 0)) for p in labels) + " |")
    fa = " · ".join(f"{k} {v:.1%}" for k, v in m["field_acc"].items())
    out = [
        f"_Auto-generated by `python code/evaluation/main.py --write-report` on {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}._",
        "",
        "| Metric | Value |", "|---|---|",
        f"| Cases (labelled samples) | {m['cases']} |",
        f"| **Case status accuracy** | **{m['status_acc']:.1%}** |",
        f"| Step precision / recall / **F1** | {m['step_p']:.1%} / {m['step_r']:.1%} / **{m['step_f1']:.1%}** |",
        f"| Evidence accuracy (on matched steps, n={m['evidence_n']}) | {m['evidence_acc']:.1%} |",
        f"| **Sequence accuracy** (exact ordered step tuples) | **{m['seq_acc']:.1%}** |",
        f"| Mean normalized Levenshtein similarity | {m['lev_sim']:.1%} |",
        f"| Exact row match (status + all steps + evidence) | {m['exact']:.1%} |",
        f"| Sample-run wall time | {runtime:.2f} s |",
        f"| Invariant violations (sample run) | {len(inv_sample)} |",
        f"| Invariant violations (root output.csv, 518 rows) | {'n/a' if inv_full is None else len(inv_full)} |",
        "", "**Field accuracy (index-aligned steps):** " + fa, "",
        "**Status confusion matrix**", "", *conf, "",
        "**Mismatched cases** (missing / extra step tuples)", "",
    ]
    if not m["mismatches"]:
        out.append("None.")
    for cid, gs, ps, miss, extra in m["mismatches"]:
        out.append(f"- `{cid}` gold={gs} pred={ps}; missing {[(t[2], t[3]) for t in miss]}; extra {[(t[2], t[3]) for t in extra]}")
    return "\n".join(out)


ABLATION_NAMES = {
    "greedy_assignment": "greedy best-pair-first instead of Hungarian optimal matching",
    "uniform_timing": "no learned timing model (one pooled Gaussian for every system)",
    "no_history": "identity uses current identifiers only (no user_audit_log)",
    "trust_claims": "believe SUCCESS activity claims as proof",
    "no_replicas": "ignore replica tables in SQL captures",
    "no_vlm": "ignore screenshot evidence",
    "no_workflow_link": "no workflow-trace linking for identifier-less resources",
    "no_scoped_absence": "no absence proofs from scoped captures",
    "rules_only_intent": "lexicon only, no LLM intent tier",
}


def custom_markdown(results) -> str:
    out = ["| Case | Fault injected | Status | Steps |", "|---|---|---|---|"]
    for r in results:
        out.append(f"| {r['case']} | {r['doc']} | {'✅' if r['status_ok'] else '❌'} | {'✅' if r['steps_ok'] else '❌'} |")
    passed = sum(r["status_ok"] and r["steps_ok"] for r in results)
    out.append(f"\n**{passed}/{len(results)} custom cases pass (exact status and steps).**")
    return "\n".join(out)


def run_ablations(base_rows) -> str:
    import exorcist.config as cfg
    from custom_cases import run_all
    sample_req = read_requests(DATASET_DIR / "sample_deletion_requests.csv")
    test_req = read_requests(DATASET_DIR / "deletion_requests.csv")
    gold = load_csv(DATASET_DIR / "sample_output.csv")
    rows = ["| Ablation (component removed) | Status acc | Step F1 | Seq acc | Custom cases passed | Test rows changed (of 518) |",
            "|---|---|---|---|---|---|"]
    naive = sum((q["reported_status"] == "COMPLETE") == (gold[q["case_id"]][0] == "COMPLETE") for q in sample_req)
    rows.append(f"| _baseline: trust the workflow's `reported_status`_ | {naive / len(sample_req):.1%} | — | — | — | — |")
    for name in [None, *ABLATION_NAMES]:
        cfg.ABLATIONS.clear()
        if name:
            cfg.ABLATIONS.add(name)
        aud = Auditor()
        pred = {r["case_id"]: (r["deletion_status"], r["steps"]) for r in aud.audit(sample_req)}
        m = score(pred, gold)
        full = {r["case_id"]: (r["deletion_status"], r["steps"]) for r in aud.audit(test_req)}
        changed = sum(full[c] != base_rows[c] for c in full)
        cust = run_all()
        passed = sum(r["status_ok"] and r["steps_ok"] for r in cust)
        failed = [r["case"].split("_", 1)[0].upper() for r in cust if not (r["status_ok"] and r["steps_ok"])]
        label = f"`{name}` — {ABLATION_NAMES[name]}" if name else "**full system**"
        rows.append(f"| {label} | {m['status_acc']:.1%} | {m['step_f1']:.1%} | {m['seq_acc']:.1%} | "
                    f"{passed}/8{' (fails ' + ', '.join(failed) + ')' if failed else ''} | {changed} |")
        print(rows[-1], flush=True)
    cfg.ABLATIONS.clear()
    return "\n".join(rows)


def calibration(rows, gold) -> str:
    """Is the per-step confidence informative? AUROC / Brier over the sample resources."""
    pairs = []
    for r in rows:
        g = {(s["system_id"], s["resource_id"], s["operation"]) for s in gold[r["case_id"]][1]}
        for key, (c, _, _) in r["trace"].get("confidence", {}).items():
            ops = {(s["system_id"], s["resource_id"], s["operation"]) for s in r["steps"]
                   if (s["system_id"], s["resource_id"]) == key}
            if ops:
                pairs.append((c, ops <= g))
    pos = [c for c, y in pairs if y]
    neg = [c for c, y in pairs if not y]
    auc = (sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))) if pos and neg else float("nan")
    brier = sum((c - y) ** 2 for c, y in pairs) / len(pairs)
    return ("| Resources scored | Correct / wrong | Mean confidence (correct) | Mean confidence (wrong) | AUROC | Brier |\n"
            "|---|---|---|---|---|---|\n"
            f"| {len(pairs)} | {len(pos)} / {len(neg)} | {sum(pos) / len(pos):.3f} | "
            f"{(sum(neg) / len(neg)) if neg else float('nan'):.3f} | {auc:.3f} | {brier:.3f} |")


def cross_validate(folds: int = 4) -> str:
    """k-fold CV of the learned timing model: fit on k-1 folds of the labelled samples,
    score only the held-out fold, so the reported gain is out-of-sample."""
    from fit_timing import fit
    sample_req = read_requests(DATASET_DIR / "sample_deletion_requests.csv")
    gold = load_csv(DATASET_DIR / "sample_output.csv")
    ids = sorted(gold, key=case_sort_key)
    aud = Auditor()
    preds = {}
    for k in range(folds):
        held = set(ids[k::folds])                       # interleaved folds
        aud.discovery.timing.params = {s: v for s, v in fit(held).items() if not s.startswith("_")}
        rows = aud.audit(sample_req)
        preds.update({r["case_id"]: (r["deletion_status"], r["steps"]) for r in rows if r["case_id"] in held})
    m = score(preds, gold)
    return (f"| {folds}-fold cross-validated (timing model never sees the scored case) | "
            f"{m['status_acc']:.1%} | {m['step_f1']:.1%} | {m['seq_acc']:.1%} | {m['evidence_acc']:.1%} |")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-report", action="store_true")
    ap.add_argument("--ablations", action="store_true", help="also run the ablation study (~2-3 min)")
    ap.add_argument("--output", type=Path, default=OUTPUT_CSV, help="full predictions to check")
    args = ap.parse_args(argv)
    sys.path.append(str(Path(__file__).resolve().parent))   # append: don't shadow code/main.py
    from custom_cases import run_all

    t0 = time.perf_counter()
    auditor = Auditor()
    sample_req = read_requests(DATASET_DIR / "sample_deletion_requests.csv")
    rows = auditor.audit(sample_req)
    runtime = time.perf_counter() - t0
    tmp = CODE / "cache" / "sample_predictions.csv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    from main import write_output  # noqa: E402
    write_output(rows, tmp)

    m = score(load_csv(tmp), load_csv(DATASET_DIR / "sample_output.csv"))
    mt = auditor.store.file_time
    inv_sample = invariants(tmp, sample_req, mt)
    inv_full = None
    if args.output.exists():
        inv_full = invariants(args.output, read_requests(DATASET_DIR / "deletion_requests.csv"), mt)

    md = metrics_markdown(m, runtime, inv_sample, inv_full)
    md += ("\n\n### Out-of-sample check of the learned component\n\n"
           "| Setting | Status acc | Step F1 | Seq acc | Evidence acc |\n|---|---|---|---|---|\n"
           f"| In-sample (timing model fit on all 32 samples) | {m['status_acc']:.1%} | {m['step_f1']:.1%} | "
           f"{m['seq_acc']:.1%} | {m['evidence_acc']:.1%} |\n" + cross_validate())
    md += ("\n\n### Confidence calibration (Bayesian evidence fusion × assignment posterior)\n\n"
           + calibration(rows, load_csv(DATASET_DIR / "sample_output.csv")))
    md += "\n\n### Custom evaluation cases (fault injection)\n\n" + custom_markdown(run_all())
    if args.ablations:
        base = {r["case_id"]: (r["deletion_status"], r["steps"])
                for r in auditor.audit(read_requests(DATASET_DIR / "deletion_requests.csv"))}
        md += "\n\n### Ablation study\n\n" + run_ablations(base)
    print(md)
    for e in (inv_sample + (inv_full or []))[:20]:
        print("INVARIANT:", e)
    if args.write_report:
        text = REPORT.read_text(encoding="utf-8") if REPORT.exists() else f"# Evaluation Report\n\n{BEGIN}\n{END}\n"
        if BEGIN not in text:
            text += f"\n{BEGIN}\n{END}\n"
        pre, rest = text.split(BEGIN, 1)
        post = rest.split(END, 1)[1]
        REPORT.write_text(f"{pre}{BEGIN}\n{md}\n{END}{post}", encoding="utf-8")
        print(f"\nupdated {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
