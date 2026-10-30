"""SQLite-compatible snapshot exports (inventories, replicas, failover, search primary)."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from ..config import ABLATIONS, INVENTORY_TABLE_SYSTEM
from ..model import SNAPSHOT, Scope, make_obs

CAPTURED_RE = re.compile(r"^--\s*Captured at:\s*(\S+)", re.M)
JSON_TABLE_RE = re.compile(r"^customer_data_(.+)$")          # customer_data_<replica>
PROFILE_TABLE_RE = re.compile(r"^customer_profiles_(primary|failover_replica)$")


def load(path: Path, evidence_id: str, manifest_time: str):
    text = path.read_text(encoding="utf-8")
    header_time = (m.group(1) if (m := CAPTURED_RE.search(text)) else None) or manifest_time
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(text)
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    scope_times: dict[str, str] = {}
    if "snapshot_scope" in tables:
        scope_times = {r["origin_system"]: r["captured_at"]
                       for r in db.execute("SELECT * FROM snapshot_scope")}

    observations, scopes = [], []
    for table in tables:
        if table == "snapshot_scope":
            continue
        rows = [dict(r) for r in db.execute(f'SELECT * FROM "{table}"')]
        if (m := JSON_TABLE_RE.match(table)) and "record_json" in (rows[0] if rows else {"record_json": 1}):
            replica = m.group(1)
            if "no_replicas" in ABLATIONS and replica != "primary":
                continue
            by_system: dict[str, set] = {}
            for row in rows:
                rec = json.loads(row["record_json"])
                system = row["origin_system"]
                by_system.setdefault(system, set()).add(row["resource_id"])
                observations.append(make_obs(
                    evidence_id, header_time, row["resource_id"], rec, system_id=system,
                    source=f"{table}.{row['collection_name']}", replica=replica))
            # A replica table enumerates every system it holds rows for.
            for system, ids in by_system.items():
                scopes.append(Scope(evidence_id, header_time, system, replica, frozenset(ids)))
            continue

        system = INVENTORY_TABLE_SYSTEM.get(table)
        if system is None:
            continue
        replica = None
        if pm := PROFILE_TABLE_RE.match(table):
            replica = pm.group(1)
        elif table == "search_documents_primary":
            replica = "primary"
        t = scope_times.get(system, header_time)
        ids = set()
        for row in rows:
            ids.add(row["resource_id"])
            observations.append(make_obs(evidence_id, t, row["resource_id"], row,
                                         system_id=system, source=table, replica=replica))
        # Inventory tables are authoritative only for systems listed in snapshot_scope;
        # replica/primary-only dumps are authoritative for their own table.
        if not scope_times or system in scope_times:
            scopes.append(Scope(evidence_id, t, system, replica, frozenset(ids)))
    db.close()
    return observations, scopes, None
