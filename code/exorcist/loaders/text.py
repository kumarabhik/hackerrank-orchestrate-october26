"""Plain-text handover records: '- ts | system | resource | RECORD_TYPE | RESULT | identifier'."""
from __future__ import annotations

import re
from pathlib import Path

from ..config import NOT_FOUND, OBS_STATUSES
from ..model import READBACK, make_obs

ROW = re.compile(r"^\s*-\s*(\S+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.*)$")


def load(path: Path, evidence_id: str, manifest_time: str):
    text = path.read_text(encoding="utf-8")
    observations = []
    for line in text.splitlines():
        if not (m := ROW.match(line)):
            continue
        ts, system, rid, record_type, result, ident = m.groups()
        observations.append(make_obs(
            evidence_id, ts, rid, {}, system_id=system, source_kind=READBACK, source="handover",
            present=result != NOT_FOUND, status=result if result in OBS_STATUSES else None,
            record_type=record_type, extra_refs=(ident.strip(),)))
    return observations, [], text
