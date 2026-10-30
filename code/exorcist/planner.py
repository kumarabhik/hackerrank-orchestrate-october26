"""Decision table → ordered FINDING / REMEDIATION / VERIFICATION steps (design_doc §6.6-6.7).

Remediation safety order (cut flows and restore paths before touching records) is
exactly the contract's operation order, so one canonical sort key serves both:
(phase rank, operation rank, system_id, resource_id).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .config import OPERATION_RANK, OPERATIONS, PHASE_RANK, RESOURCE_ID_RE
from .policy import ANONYMIZE, BACKUP, DELETE, FLOW, REDACT, RETAIN
from .state import ResourceState

FINDING_OP = {
    DELETE: "REPORT_REMAINING_RECORD", REDACT: "REPORT_EXPOSED_PII",
    ANONYMIZE: "REPORT_EXPOSED_PII", FLOW: "REPORT_ACTIVE_DATA_FLOW", BACKUP: "REPORT_RESTORE_RISK",
}
REMEDIATION_OP = {
    DELETE: "DELETE_RECORD", REDACT: "REDACT_RECORD", ANONYMIZE: "ANONYMIZE_RECORD",
    FLOW: "DISABLE_DATA_FLOW", BACKUP: "BLOCK_RESTORE",
}
VERIFY_OP = {
    DELETE: "VERIFY_RECORD_ABSENT", REDACT: "VERIFY_RECORD_REDACTED",
    ANONYMIZE: "VERIFY_RECORD_ANONYMIZED", RETAIN: "VERIFY_RECORD_PRESENT",
    FLOW: "VERIFY_DATA_FLOW_DISABLED", BACKUP: "VERIFY_RESTORE_BLOCKED",
}
# Business registers (order/finance rows) link identities to records but are not
# remediable customer-data resources.
EVIDENCE_ONLY_SYSTEMS = {"legal_service"}
STEP_KEYS = ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")


@dataclass
class Item:
    state: ResourceState
    treatment: str
    violation: bool
    evidence: str            # proof of the violation, or of the compliant state
    reasons: set


def _latest(state: ResourceState, pred):
    obs = [o for o in state.observations if o.source_kind != "activity" and pred(o)]
    return max(obs, key=lambda o: (o.observed_at, o.evidence_id)) if obs else None


def assess(state: ResourceState, treatment: str, audit_at: str) -> tuple[bool, str]:
    """(is_violation, evidence_id proving the current state)."""
    if treatment == RETAIN:
        return False, state.proof or ""
    if treatment == DELETE:
        return bool(state.exists), state.proof or ""
    if treatment in (REDACT, ANONYMIZE):
        last = _latest(state, lambda o: o.present is not False and o.status is not None)
        if last is None:
            return False, state.proof or ""
        return last.status == "IDENTIFIABLE", last.evidence_id
    if treatment in (FLOW, BACKUP):
        proof = state.attrs.get("status_proof")
        return state.status == "ACTIVE", (proof[0] if proof else state.proof or "")
    return False, ""


def _ever(state: ResourceState, pred) -> bool:
    return any(o.source_kind != "activity" and pred(o) for o in state.observations)


def relevant(state: ResourceState, treatment: str, violation: bool, reasons: set) -> bool:
    """Which compliant resources deserve a verification step."""
    if not RESOURCE_ID_RE.fullmatch(state.resource_id or ""):
        return False                                  # business refs (orders) are not resources
    if state.system_id in EVIDENCE_ONLY_SYSTEMS:
        return False
    if violation:
        return True
    if treatment == RETAIN:
        return bool(state.exists)
    if state.system_id == "identity_service":
        return bool(state.exists)                     # a tombstone must stay, holding only user_id
    if state.workflow_actions:
        return True                                   # the workflow claimed to treat it
    if treatment == DELETE:
        return _ever(state, lambda o: o.present is True)
    if treatment in (REDACT, ANONYMIZE):
        return _ever(state, lambda o: o.status == "IDENTIFIABLE")
    return _ever(state, lambda o: o.status == "ACTIVE")


def build_steps(items: list[Item], status: str) -> list[dict]:
    raw = []
    for it in items:
        sysid, rid = it.state.system_id, it.state.resource_id
        if status == "INCOMPLETE" and it.violation:
            raw.append(("FINDING", FINDING_OP[it.treatment], sysid, rid, it.evidence))
            raw.append(("REMEDIATION", REMEDIATION_OP[it.treatment], sysid, rid, ""))
        ev = it.evidence if status == "COMPLETE" else ""
        raw.append(("VERIFICATION", VERIFY_OP[it.treatment], sysid, rid, ev))
    raw.sort(key=lambda r: (PHASE_RANK[r[0]], OPERATION_RANK[r[1]], r[2], r[3]))
    steps = []
    for i, (phase, op, sysid, rid, ev) in enumerate(raw, 1):
        assert OPERATIONS[op][0] == phase
        steps.append(dict(zip(STEP_KEYS, (i, phase, sysid, rid, op, OPERATIONS[op][1], ev))))
    return steps


def serialize(steps: list[dict]) -> str:
    return json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
