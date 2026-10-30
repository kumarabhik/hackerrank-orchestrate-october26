"""JSON evidence: snapshot bundles, record-style exports, service resource exports,
and flat collections (analytics report, export jobs)."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import NOT_FOUND, OBS_STATUSES, canonical_system
from ..model import READBACK, SNAPSHOT, Scope, make_obs

ABSENT_RESULTS = {NOT_FOUND}


def _record_style(data, evidence_id, observations):
    """{records:[{recorded_at, system, resource_id, record_type, result, subject_reference}]}"""
    for r in data["records"]:
        result = r.get("result")
        observations.append(make_obs(
            evidence_id, r.get("recorded_at") or data.get("exported_at"), r["resource_id"], {},
            system_id=r.get("system"), source_kind=READBACK,
            source=data.get("origin", "record_export"),
            present=result not in ABSENT_RESULTS,
            status=result if result in OBS_STATUSES else None,
            record_type=r.get("record_type"), extra_refs=(r.get("subject_reference"),)))


def _bundle(data, evidence_id, observations, scopes):
    start = len(observations)
    pending = []
    for snap in data["snapshots"]:
        system = canonical_system(snap["data_store"])
        t = snap.get("captured_at") or data.get("exported_at")
        ids = set()
        for rec in snap["records"]:
            ids.add(rec["resource_id"])
            observations.append(make_obs(evidence_id, t, rec["resource_id"], rec,
                                         system_id=system, source=snap["collection"]))
        pending.append((t, system, frozenset(ids)))
    # A bundle is assembled for specific subjects: its gaps prove absence only for them.
    subjects = frozenset(k for o in observations[start:] for k in o.refs
                         if not k.startswith("name:"))
    for t, system, ids in pending:
        scopes.append(Scope(evidence_id, t, system, None, ids, subjects))


def _service_export(data, evidence_id, observations):
    for system, collections in data["service_exports"].items():
        for coll, entries in collections.items():
            for e in entries:
                t = e.get("observed_at") or data.get("exported_at")
                rid = e["resource_id"]
                if "status_code" in e:                      # account profile lookups
                    present = e["status_code"] != 404 and e.get("profile") is not None
                    rec = e.get("profile") or {}
                    observations.append(make_obs(evidence_id, t, rid, rec, system_id=system,
                                                 source_kind=READBACK, source=coll, present=present))
                elif "hits" in e:                           # search index queries
                    docs = e["hits"].get("documents") or []
                    match = [d for d in docs if d.get("resource_id") == rid]
                    rec = match[0] if match else {}
                    observations.append(make_obs(evidence_id, t, rid, rec, system_id=system,
                                                 source_kind=READBACK, source=coll,
                                                 present=bool(match),
                                                 extra_refs=(e.get("query"),)))
                else:
                    observations.append(make_obs(evidence_id, t, rid, e, system_id=system,
                                                 source_kind=READBACK, source=coll))


def _flat(data, evidence_id, observations):
    t = data.get("captured_at") or data.get("exported_at")
    for rec in data["records"]:
        observations.append(make_obs(evidence_id, t, rec["resource_id"], rec,
                                     source=data.get("collection", "")))


def load(path: Path, evidence_id: str, manifest_time: str):
    data = json.loads(path.read_text(encoding="utf-8"))
    observations, scopes = [], []
    if "snapshots" in data:
        _bundle(data, evidence_id, observations, scopes)
    elif "service_exports" in data:
        _service_export(data, evidence_id, observations)
    elif data.get("records") and "record_type" in data["records"][0]:
        _record_style(data, evidence_id, observations)
    elif "records" in data:
        _flat(data, evidence_id, observations)
    return observations, scopes, None
