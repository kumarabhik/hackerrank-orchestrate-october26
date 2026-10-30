"""Screenshot evidence via the vision model (design_doc §6.1).

Extraction runs once per image and is cached by content hash (llm.py), so the
pipeline stays deterministic and offline-capable once the cache exists. Extracted
rows are validated before they become observations: identifiers must look like a
real resource id (or a document reference resolvable through catalog aliases);
order numbers, ticket numbers and free text are discarded, never guessed.
"""
from __future__ import annotations

from pathlib import Path

from ..config import DOC_REF_RE, RESOURCE_ID_RE
from ..llm import shared
from ..model import SCREENSHOT, make_obs


def load(path: Path, evidence_id: str, manifest_time: str):
    data = shared().extract_screenshot(path)
    if not isinstance(data, dict):
        return [], [], None
    subject = data.get("subject") or {}
    observations, lines = [], []
    for rec in data.get("records") or []:
        rid = (rec.get("resource_id") or "").strip()
        if not rid or " " in rid:
            continue
        # resource ids get their system from the prefix; anything else (file names,
        # user references) stays unbound and only survives if a catalog alias maps it
        # to a real resource (e.g. user_17 -> tombstone_17); otherwise it is dropped
        system = None
        if not (RESOURCE_ID_RE.fullmatch(rid) or DOC_REF_RE.fullmatch(rid) or "_" in rid):
            continue
        record = {k: rec.get(k) for k in ("name", "email", "phone", "email_hash")}
        record["customer_reference"] = rec.get("user_id")
        # a page about one customer: rows without their own identity belong to that customer
        if not any(record.values()) and str(subject.get("user_id") or "").startswith("user_"):
            record["customer_reference"] = subject["user_id"]
        for flag in ("enabled", "restore_allowed"):
            if isinstance(rec.get(flag), bool):
                record[flag] = rec[flag]
        status = str(rec.get("status") or "").lower()
        if rid.startswith("backup_") and "restore_allowed" not in record:
            # an archive listed in a recovery console is restorable unless marked otherwise
            record["restore_allowed"] = not any(w in status for w in ("block", "restrict", "hold", "disabled"))
        observations.append(make_obs(evidence_id, manifest_time, rid, record, system_id=system,
                                     source_kind=SCREENSHOT, source=data.get("screen", path.stem)[:40]))
        lines.append(" ".join(str(v) for v in rec.values() if v))
    return observations, [], "\n".join(lines)
