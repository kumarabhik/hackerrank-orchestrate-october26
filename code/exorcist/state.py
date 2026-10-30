"""Temporal state reconstruction at audit_at (design_doc §6.5).

Evidence-strength lattice: direct observations (snapshot / readback / document /
screenshot, and absence proven by a scoped capture) decide state; activity claims
never do. Each replica is judged separately (replica drift): a resource exists if
ANY copy still exists. A delete claim followed by a sync/restore and a later
sighting is flagged as a resurrection.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache

from .config import ABLATIONS
from .model import ACTIVITY, Observation
from .store import Store

# trust_claims ablation only: what a SUCCESS claim would assert if believed
CLAIM_EFFECT = {"DELETE_RECORD": (False, "NOT_FOUND"), "ANONYMIZE_RECORD": (True, "ANONYMIZED"),
                "REDACT_RECORD": (True, "REDACTED"), "DISABLE_DATA_FLOW": (True, "DISABLED"),
                "BLOCK_RESTORE": (True, "BLOCKED")}

RESURRECTING_EVENTS = {"SYNC_RECORD", "RESTORE_BACKUP"}
WORKFLOW_ACTIONS = {"DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD", "DISABLE_DATA_FLOW",
                    "BLOCK_RESTORE", "RETAIN_RECORD", "CHECK_DATA_FLOW", "CHECK_RESTORE_ACCESS"}


@dataclass
class ResourceState:
    system_id: str
    resource_id: str
    exists: bool | None = None          # None = never directly observed
    status: str | None = None           # latest direct status (FOUND/IDENTIFIABLE/ACTIVE/...)
    record_type: str | None = None      # latest explicit record_type
    proof: str | None = None            # evidence id that decided `exists`/`status`
    proof_time: str | None = None
    replicas: dict = field(default_factory=dict)   # replica -> (present, evidence_id, time)
    workflow_actions: list = field(default_factory=list)  # deletion-worker event types
    resurrected: bool = False
    attrs: dict = field(default_factory=dict)
    observations: list = field(default_factory=list)


PROCESS_STATUSES = {"ACTIVE", "DISABLED", "BLOCKED"}


def visible(store: Store, evidence_id: str, t: str, audit_at: str) -> bool:
    """Usable at audit_at: the fact and the evidence file itself predate the cutoff."""
    file_time = store.file_time.get(evidence_id, t)
    return t <= audit_at and file_time <= audit_at


# A point-in-time audit is decided by recent captures: a months-old snapshot cannot
# establish what exists *now* (every citation in the labelled samples is ≤ 5 days old).
FRESHNESS = timedelta(days=30)


@lru_cache(maxsize=4096)
def freshness_floor(audit_at: str) -> str:
    t = datetime.fromisoformat(audit_at.replace("Z", "+00:00")) - FRESHNESS
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def reconstruct(store: Store, key: tuple, audit_at: str, subject_keys=frozenset()) -> ResourceState:
    system, rid = key
    st = ResourceState(system, rid)
    floor = freshness_floor(audit_at)
    obs = [o for o in store.by_resource.get(key, [])
           if visible(store, o.evidence_id, o.observed_at, audit_at)
           and (o.source_kind == ACTIVITY or o.observed_at >= floor)]
    st.observations = obs

    # Events per replica group: (time, present, evidence_id, observation-or-None)
    events: dict[str, list] = {}
    for o in obs:
        if o.source_kind == ACTIVITY:
            et = o.attrs.get("event_type")
            if o.attrs.get("source_system") == "deletion_worker" and et in WORKFLOW_ACTIONS:
                st.workflow_actions.append(et)
            continue
        if o.present is None:
            continue
        events.setdefault(o.replica or "primary", []).append((o.observed_at, o.present, o.evidence_id, o))
    scopes = store.scopes.get(system, [])
    times = store.scope_times.get(system, [])
    # O(log n) to the captures inside [floor, audit_at] instead of scanning every capture
    window = scopes[bisect_left(times, floor):bisect_right(times, audit_at)]
    for sc in ([] if "no_scoped_absence" in ABLATIONS else window):
        if not visible(store, sc.evidence_id, sc.observed_at, audit_at) or rid in sc.resource_ids:
            continue
        if sc.subjects and not (sc.subjects & subject_keys):
            continue                                 # subject-scoped capture of someone else
        if not sc.subjects and not sc.resource_ids:
            continue                                 # empty global capture: too weak to prove absence
        events.setdefault(sc.replica or "primary", []).append((sc.observed_at, False, sc.evidence_id, None))

    latest_overall = None
    for replica, evs in events.items():
        evs.sort(key=lambda e: (e[0], e[1] is False, e[2]))   # same instant: absence after presence
        t, present, eid, o = evs[-1]
        st.replicas[replica] = (present, eid, t)
        if latest_overall is None or (t, eid) > (latest_overall[0], latest_overall[2]):
            latest_overall = (t, present, eid, o)

    if st.replicas:
        alive = {r: v for r, v in st.replicas.items() if v[0]}
        st.exists = bool(alive)
        if alive:   # the most recent copy that still holds the data is the proof
            r, (p, eid, t) = max(alive.items(), key=lambda kv: (kv[1][2], kv[1][1]))
        else:
            r, (p, eid, t) = max(st.replicas.items(), key=lambda kv: (kv[1][2], kv[1][1]))
        st.proof, st.proof_time = eid, t

    direct = [o for o in obs if o.source_kind != ACTIVITY]
    if direct:
        last = max(direct, key=lambda o: (o.observed_at, o.evidence_id))
        st.status = last.status
        # processes (flows, restore paths): only observations that state the process
        # status count; a plain 'record found' line says nothing about enabled/blocked
        proc = [o for o in direct if o.status in PROCESS_STATUSES]
        if proc:
            p = max(proc, key=lambda o: (o.observed_at, o.evidence_id))
            st.status, st.attrs["status_proof"] = p.status, (p.evidence_id, p.observed_at)
        for o in sorted(direct, key=lambda o: o.observed_at):
            st.attrs.update(o.attrs)
            if o.record_type:
                st.record_type = o.record_type
    # status-bearing observations (e.g. flow ACTIVE) without presence semantics
    if st.exists is None and direct:
        st.exists = True
        st.proof, st.proof_time = last.evidence_id, last.observed_at

    if "trust_claims" in ABLATIONS:
        # naive dashboard baseline: a SUCCESS claim is taken as the final state, overriding evidence
        claims = [o for o in obs if o.attrs.get("event_type") in CLAIM_EFFECT
                  and o.attrs.get("reported_result") == "SUCCESS"]
        if claims:
            c = max(claims, key=lambda o: o.observed_at)
            st.exists, st.status = CLAIM_EFFECT[c.attrs["event_type"]]
            st.proof = c.evidence_id
            fake = Observation(c.evidence_id, c.observed_at, system, rid, "readback", "claim",
                               None, st.exists, st.status)
            st.observations = st.observations + [fake]
            st.attrs["status_proof"] = (c.evidence_id, c.observed_at)

    # resurrection: delete claim, then a sync/restore, then the data observed again
    deletes = [o.observed_at for o in obs if o.attrs.get("event_type") == "DELETE_RECORD"]
    revives = [o.observed_at for o in obs if o.attrs.get("event_type") in RESURRECTING_EVENTS]
    if st.exists and deletes and any(r > min(deletes) for r in revives):
        st.resurrected = True
    return st
