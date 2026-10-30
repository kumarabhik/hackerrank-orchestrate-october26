"""Dispatch every manifest file to its format loader."""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import ABLATIONS, DATASET_DIR
from . import activity, images, json_, logs, pdf, sql, text

LOADERS = {".sql": sql.load, ".json": json_.load, ".log": logs.load, ".txt": text.load,
           ".pdf": pdf.load, ".png": images.load}


def read_manifest(dataset_dir: Path = DATASET_DIR) -> list[dict]:
    with (dataset_dir / "evidence_files.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_evidence(dataset_dir: Path = DATASET_DIR):
    """Return (observations, scopes, texts, per_file_counts, skipped)."""
    observations, scopes, texts, counts, skipped = [], [], {}, {}, []
    for row in read_manifest(dataset_dir):
        path = dataset_dir / row["file_path"]
        loader = LOADERS.get(path.suffix.lower())
        if path.suffix.lower() == ".png" and "no_vlm" in ABLATIONS:
            loader = None
        if loader is None:
            skipped.append(row["file_id"])
            counts[row["file_id"]] = 0
            continue
        obs, scp, txt = loader(path, row["file_id"], row["captured_at"])
        observations.extend(obs)
        scopes.extend(scp)
        if txt:
            texts[row["file_id"]] = txt
        counts[row["file_id"]] = len(obs)
    act = activity.load(dataset_dir / "system_activity.csv")
    observations.extend(act)
    counts["system_activity.csv"] = len(act)
    return observations, scopes, texts, counts, skipped
