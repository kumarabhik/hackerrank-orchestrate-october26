"""Core data contracts shared by every stage."""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import (
    ACTIVE, ANONYMIZED, BLOCKED, DISABLED, FOUND, IDENTIFIABLE, NOT_FOUND, REDACTED,
    canonical_system, system_for_resource,
)
from .ids import DIRECT_PII_FIELDS, classify, name_key

# source_kind values, strongest first (evidence-strength lattice, design_doc §6.5)
SNAPSHOT, READBACK, DOCUMENT, SCREENSHOT, ACTIVITY = (
    "snapshot", "readback", "document", "screenshot", "activity",
)


@dataclass(slots=True)
class Observation:
    """One fact seen by one piece of evidence at one time."""
    evidence_id: str                  # file_id | activity_id | audit_id
    observed_at: str                  # ISO-8601 'Z' string (lexicographically comparable)
    system_id: str | None
    resource_id: str
    source_kind: str
    source: str = ""                  # table / collection / log event, for explain mode
    replica: str | None = None        # primary, read_replica, failover_replica, ...
    present: bool | None = None       # True found, False proven absent, None = claim only
    status: str | None = None         # normalized status (config.OBS_STATUSES)
    record_type: str | None = None    # policy data_category when known
    pii: dict = field(default_factory=dict)   # name/email/phone/email_hash/user_ref values
    refs: set = field(default_factory=set)    # typed identifier keys linking this resource
    attrs: dict = field(default_factory=dict) # enabled, restore_allowed, retention_until, ...


@dataclass(slots=True)
class Scope:
    """Evidence that enumerated a whole system (or replica) at one time: absence of a
    resource from a scoped capture is proof of absence at that time."""
    evidence_id: str
    observed_at: str
    system_id: str
    replica: str | None
    resource_ids: frozenset
    # Empty = a global capture (SQL snapshots). Otherwise the capture was taken for
    # these subjects only (snapshot bundles) and proves absence only for them.
    subjects: frozenset = frozenset()


PII_KEY_MAP = {
    "full_name": "name", "name": "name", "display_name": "name", "requester_name": "name",
    "email": "email", "customer_email": "email", "owner_email": "email",
    "requester_email": "email", "matched_value": "email",
    "phone": "phone", "owner_phone": "phone", "requester_phone": "phone",
    "email_hash": "email_hash",
    "customer_reference": "user_ref", "user_id": "user_ref", "subject_reference": "user_ref",
    "correlation_key": "user_ref", "subject_ref": "user_ref",
}
NESTED_RECORD_KEYS = ("document", "profile", "customer", "subject")


def _null(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in {"", "null", "none"})


def extract_pii(record: dict) -> dict:
    """Map heterogeneous field names onto name/email/phone/email_hash/user_ref."""
    out: dict = {}
    flat = dict(record)
    for nk in NESTED_RECORD_KEYS:                 # e.g. search {"document": {...}}
        if isinstance(record.get(nk), dict):
            flat = {**record[nk], **flat}
    for k, v in flat.items():
        tgt = PII_KEY_MAP.get(k)
        if tgt and not _null(v) and isinstance(v, str):
            if tgt == "email" and classify(v) is None:
                continue          # e.g. matched_value holding a non-email
            if tgt == "user_ref" and not v.startswith("user_"):
                kind = classify(v)  # subject_reference may hold an email
                if kind and kind.startswith("email:"):
                    out.setdefault("email", v)
                continue
            out.setdefault(tgt, v)
    return out


def refs_from(pii: dict, *extra) -> set:
    refs = set()
    for k, v in pii.items():
        key = name_key(v) if k == "name" else classify(v)
        if key:
            refs.add(key)
    for v in extra:
        key = classify(v) if isinstance(v, str) else None
        if key:
            refs.add(key)
    return refs


def derive_status(system_id: str | None, pii: dict, attrs: dict, present: bool | None) -> str | None:
    """Normalized status from raw record content (evidence that states it explicitly wins)."""
    if present is False:
        return NOT_FOUND
    if system_id == "integration_service" and "enabled" in attrs:
        return ACTIVE if attrs["enabled"] else DISABLED
    if system_id == "backup_service" and "restore_allowed" in attrs:
        return ACTIVE if attrs["restore_allowed"] else BLOCKED
    direct = any(pii.get(f) for f in DIRECT_PII_FIELDS)
    if system_id == "analytics_platform":
        return IDENTIFIABLE if direct or pii.get("user_ref") else ANONYMIZED
    if system_id in ("support_platform", "identity_service"):
        return IDENTIFIABLE if direct else REDACTED
    return FOUND if present else None


def to_bool(v) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "enabled"}:
        return True
    if s in {"0", "false", "no", "disabled"}:
        return False
    return None


def make_obs(evidence_id, observed_at, resource_id, record: dict, *, system_id=None,
             source_kind=SNAPSHOT, source="", replica=None, present=True,
             status=None, record_type=None, extra_refs=()) -> Observation:
    """Build an Observation from a raw record dict, normalizing PII/flags/status."""
    system = canonical_system(system_id) or system_for_resource(resource_id)
    pii = extract_pii(record)
    attrs = {}
    for k in ("enabled", "restore_allowed"):
        if k in record and to_bool(record[k]) is not None:
            attrs[k] = to_bool(record[k])
    for k in ("retention_until", "account_status", "message_excerpt", "connector_name",
              "last_delivery_status", "event_code", "event_name", "archive_key",
              "object_key", "source_resource_id", "index_name", "audience_cohort"):
        if k in record and not _null(record[k]):
            attrs[k] = record[k]
    if status is None:
        status = derive_status(system, pii, attrs, present)
    # record_type stays None unless the evidence states it; policy applies system defaults.
    refs = refs_from(pii, *extra_refs)
    return Observation(evidence_id, observed_at, system, resource_id, source_kind, source,
                       replica, present, status, record_type, pii, refs, attrs)
