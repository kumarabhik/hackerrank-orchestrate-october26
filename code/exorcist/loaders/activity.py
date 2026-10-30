"""system_activity.csv: every row is a claim about a resource (tier-2 evidence), except
explicit checks (CHECK_DATA_FLOW / CHECK_RESTORE_ACCESS) which observe current risk,
and LINK_RESOURCE_IDENTITY rows which link resources to identifiers."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from ..config import ACTIVE, RESOURCE_ID_RE, canonical_system, system_for_resource
from ..ids import EMAIL_RE
from ..model import ACTIVITY, READBACK, Observation, refs_from

USER_RE = re.compile(r"\buser_\d+\b")
ALIAS_RE = re.compile(r"\b\w+_\d+ \(([^)]+)\)")

CHECK_EVENTS = {"CHECK_DATA_FLOW", "CHECK_RESTORE_ACCESS"}


def load(path: Path):
    observations = []
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            et, details = r["event_type"], r["details"]
            rid = r["resource_id"]
            system = system_for_resource(rid) or canonical_system(r["target_system"])
            pii = {}
            if emails := EMAIL_RE.findall(details):
                pii["email"] = emails[0]
            if users := USER_RE.findall(details):
                pii["user_ref"] = users[0]
            linked = sorted(set(RESOURCE_ID_RE.findall(details)) - {rid})
            attrs = {
                "event_type": et,
                "reported_result": r["reported_result"],
                "source_system": r["source_system"],
                "target_system": r["target_system"],
                "details": details,
            }
            if linked:
                attrs["linked_resources"] = linked
            if et == "LINK_RESOURCE_IDENTITY" and (m := ALIAS_RE.search(details)):
                attrs["alias"] = m.group(1)
            if "belongs only to" in details:
                attrs["sole_subject"] = True
            if "non-deletion" in details:
                attrs["non_deletion"] = True
            is_check = et in CHECK_EVENTS
            observations.append(Observation(
                evidence_id=r["activity_id"], observed_at=r["event_time"], system_id=system,
                resource_id=rid, source_kind=READBACK if is_check else ACTIVITY, source=et,
                present=True if is_check else None, status=ACTIVE if is_check else None,
                record_type=None, pii=pii, refs=refs_from(pii), attrs=attrs))
    return observations
