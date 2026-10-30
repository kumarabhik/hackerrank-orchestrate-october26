"""Candidate-resource discovery for one deletion subject.

Two signals, both grounded in participant evidence:
1. Identifier links: any observation (≤ audit_at) whose refs contain one of the
   subject's identifiers as of audit_at (emails, phones, hashes, user_id).
2. Workflow trace: the deletion workflow that produced `reported_status` acted on the
   subject's resources around `reported_at`. Resources it touched are added only if
   no evidence ties them to a different user (their identifiers are often already
   gone, e.g. a deleted account or an anonymized analytics profile).
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

from .assignment import INF, UNSEEN_PENALTY, TimingModel, optimal_matching
from .config import ABLATIONS
from .identity import IdentityGraph
from .model import ACTIVITY
from .store import Store

WORKFLOW_SOURCES = {"deletion_worker"}
WORKFLOW_WINDOW = timedelta(hours=2)


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Discovery:
    def __init__(self, store: Store, identity: IdentityGraph):
        self.store, self.identity = store, identity
        self.timing = TimingModel()
        self.link_prob: dict[tuple, float] = {}     # (uid, resource) -> P(owner | timing)
        # all-time owners of each resource from its non-name identifiers
        self.res_owners: dict[tuple, set] = {}
        for key, obs in store.by_resource.items():
            refs = set().union(*(o.refs for o in obs))
            self.res_owners[key] = identity.owners(refs)
        self.workflow = sorted(
            (o for o in store.observations
             if o.attrs.get("source_system") in WORKFLOW_SOURCES),
            key=lambda o: o.observed_at)
        self._workflow_ts = [_ts(o.observed_at) for o in self.workflow]

    def by_identifiers(self, keys: set, audit_at: str) -> tuple[set, set]:
        """(linked by evidence visible at audit_at, linked only by later evidence)."""
        found, later = set(), set()
        for k in keys:
            for res in self.store.by_identifier.get(k, ()):
                obs = [o for o in self.store.by_resource[res] if k in o.refs]
                if any(o.observed_at <= audit_at and
                       self.store.file_time.get(o.evidence_id, o.observed_at) <= audit_at for o in obs):
                    found.add(res)
                elif obs:
                    later.add(res)
        return found, later - found

    def by_workflow(self, uid: str, reported_at: str, audit_at: str) -> set:
        import bisect
        if "no_workflow_link" in ABLATIONS:
            return set()
        t = _ts(reported_at)
        lo = bisect.bisect_left(self._workflow_ts, t - WORKFLOW_WINDOW)
        hi = bisect.bisect_right(self._workflow_ts, t + WORKFLOW_WINDOW)
        found = set()
        for o in self.workflow[lo:hi]:
            if o.observed_at > audit_at:
                continue
            key = (o.system_id, o.resource_id)
            owners = self.res_owners.get(key, set())
            if not owners or owners == {uid}:
                found.add(key)
        return found

    def candidates(self, uid: str, reported_at: str, audit_at: str) -> dict[tuple, set]:
        """(system, resource) -> set of reasons ('identifier' / 'workflow'), unresolved."""
        keys = self.identity.keys_at(uid, audit_at)
        out: dict[tuple, set] = defaultdict(set)
        found, later = self.by_identifiers(keys, audit_at)
        for res, tag in [(r, "identifier") for r in found] + [(r, "identifier-later") for r in later]:
            if self.res_owners.get(res, set()) - {uid} and uid not in self.res_owners.get(res, set()):
                continue
            out[res].add(tag)
        for res in self.by_workflow(uid, reported_at, audit_at):
            out[res].add("workflow")
        return dict(out)

    def _directly_seen(self, res: tuple, audit_at: str) -> bool:
        """Some non-activity evidence visible at audit_at observed this resource."""
        return any(o.source_kind != ACTIVITY and o.observed_at <= audit_at
                   and self.store.file_time.get(o.evidence_id, o.observed_at) <= audit_at
                   for o in self.store.by_resource[res])

    def _workflow_gap(self, res: tuple, reported_at: str) -> float:
        t = _ts(reported_at)
        return min(abs((_ts(o.observed_at) - t).total_seconds())
                   for o in self.store.by_resource[res]
                   if o.attrs.get("source_system") in WORKFLOW_SOURCES)

    def resolve_all(self, subjects: dict[str, tuple]) -> dict[str, dict]:
        """subjects: case_id -> (uid, reported_at, audit_at).

        Workflow-only resources are contested between requests whose workflow windows
        overlap; each goes to the request(s) with the smallest timing gap. A subject has
        one primary account: identifier-linked accounts win, else the best-timed one."""
        raw = {cid: self.candidates(*args) for cid, args in subjects.items() if args[0]}
        out = {cid: {r: w for r, w in c.items() if w & {"identifier", "identifier-later"}}
               for cid, c in raw.items()}
        # Resources linked only through the workflow are a fallback, assigned one-to-one:
        # each resource to one request, each request at most one per system, and never
        # into a system where the request already has an identifier-linked resource.
        # Claimants are people, not requests: two requests from the same subject (a
        # duplicate or follow-up) share that subject's resources instead of competing.
        offers = []
        for cid, cands in raw.items():
            uid, rep, audit_at = subjects[cid]
            linked_systems = {r[0] for r, w in cands.items() if "identifier" in w}
            for res, why in cands.items():
                if why == {"workflow"} and res[0] not in linked_systems:
                    offers.append((not self._directly_seen(res, audit_at),
                                   self._workflow_gap(res, rep), res[1], uid, cid, res))
        if "greedy_assignment" in ABLATIONS:
            return self._assign_greedy(offers, out)
        return self._assign_optimal(offers, subjects, out)

    def _assign_greedy(self, offers, out):
        """Baseline: best (seen, gap) pair first. Kept as an ablation."""
        taken_res, taken_slot = {}, set()
        for *_, uid, cid, res in sorted(offers, key=lambda o: o[:4]):
            owner = taken_res.get(res)
            if owner is None and (uid, res[0]) not in taken_slot:
                taken_res[res] = uid
                taken_slot.add((uid, res[0]))
                owner = uid
            if owner == uid:
                out[cid][res] = {"workflow"}
        return out

    def _assign_optimal(self, offers, subjects, out):
        """Hungarian matching per system minimizing total timing negative log-likelihood
        (see assignment.py)."""
        cost: dict[str, dict] = defaultdict(dict)        # system -> (uid, res) -> cost
        for unseen, _, _, uid, cid, res in offers:
            rep = subjects[cid][1]
            c = UNSEEN_PENALTY * unseen + self._workflow_nll(res, rep)
            key = (uid, res)
            cost[res[0]][key] = min(c, cost[res[0]].get(key, INF))
        owner = {}
        for system, sys_offers in cost.items():
            for uid, res in optimal_matching(sys_offers).items():
                owner[res] = uid
            # posterior over claimants of each resource: softmax of −cost
            by_res: dict = defaultdict(dict)
            for (uid, res), c in sys_offers.items():
                by_res[res][uid] = c
            for res, claims in by_res.items():
                lo = min(claims.values())
                z = sum(math.exp(-(c - lo)) for c in claims.values())
                for uid, c in claims.items():
                    self.link_prob[(uid, res)] = math.exp(-(c - lo)) / z
        for _, _, _, uid, cid, res in offers:
            if owner.get(res) == uid:
                out[cid][res] = {"workflow"}
        return out

    def _workflow_nll(self, res: tuple, reported_at: str) -> float:
        t = _ts(reported_at)
        return min(self.timing.nll(res[0], (_ts(o.observed_at) - t).total_seconds() / 3600)
                   for o in self.store.by_resource[res]
                   if o.attrs.get("source_system") in WORKFLOW_SOURCES)
