"""Fit the workflow timing model (offline, on the PUBLIC labelled samples only).

    python code/evaluation/fit_timing.py   -> code/exorcist/timing_model.json

For each system we model the offset (hours) between a deletion-workflow action on a
subject's resource and that request's `reported_at` as a Gaussian. Per-system
estimates are shrunk toward the pooled estimate (normal–normal empirical Bayes with
pseudo-count K): small systems (n=2) borrow strength, large ones keep their own shape.

    mu_s    = (n_s * mean_s + K * mu_0) / (n_s + K)
    var_s   = (n_s * var_s  + K * var_0) / (n_s + K)

Only parameters are shipped; no case identifiers or answers.
"""
from __future__ import annotations

import csv
import json
import statistics as st
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"
OUT = ROOT / "code" / "exorcist" / "timing_model.json"
K = 3.0                  # prior pseudo-count
MIN_SIGMA = 0.25         # hours; guards against degenerate fits


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    model = fit()
    OUT.write_text(json.dumps(model, indent=1), encoding="utf-8")
    for k, v in model.items():
        print(k, v)


def fit(exclude: set = frozenset()) -> dict:
    """Fit on all labelled samples except `exclude` (used for k-fold cross-validation)."""
    with (DATA / "system_activity.csv").open(encoding="utf-8", newline="") as fh:
        acts = [a for a in csv.DictReader(fh) if a["source_system"] == "deletion_worker"]
    by_res = {}
    for a in acts:
        by_res.setdefault(a["resource_id"], []).append(a)
    with (DATA / "sample_deletion_requests.csv").open(encoding="utf-8", newline="") as fh:
        req = {r["case_id"]: r for r in csv.DictReader(fh)}
    offsets: dict[str, list] = {}
    with (DATA / "sample_output.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["case_id"] in exclude:
                continue
            rep = ts(req[row["case_id"]]["reported_at"])
            for res in {s["resource_id"] for s in json.loads(row["steps_json"])}:
                for a in by_res.get(res, []):
                    offsets.setdefault(a["target_system"], set()).add(
                        round((ts(a["event_time"]) - rep).total_seconds() / 3600, 3))
    pooled = [x for v in offsets.values() for x in v]
    mu0, var0 = st.mean(pooled), st.pvariance(pooled)
    model = {"_prior": {"mu": mu0, "sigma": var0 ** 0.5, "n": len(pooled), "K": K},
             "_provenance": "fit_timing.py on sample_output.csv + system_activity.csv (public samples)"}
    for system, vals in sorted(offsets.items()):
        v = list(vals)
        n = len(v)
        mu = (n * st.mean(v) + K * mu0) / (n + K)
        var = (n * st.pvariance(v) + K * var0) / (n + K)
        model[system] = {"mu": round(mu, 4), "sigma": round(max(var ** 0.5, MIN_SIGMA), 4), "n": n}
    return model


if __name__ == "__main__":
    main()
