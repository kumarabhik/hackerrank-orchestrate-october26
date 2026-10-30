"""End-to-end auditor: compile once, then decide every case (design_doc §7)."""
from __future__ import annotations

import csv
import time
from pathlib import Path

from .config import ABLATIONS, DATASET_DIR
from .discovery import Discovery
from .identity import IdentityGraph
from .intent import IntentGate
from .llm import shared
from .confidence import link_confidence, state_confidence
from .config import RESOURCE_ID_RE
from .planner import EVIDENCE_ONLY_SYSTEMS, Item, assess, build_steps, relevant
from .policy import DELETE, RETAIN, Policy
from .state import reconstruct
from .store import Store


def case_sort_key(case_id: str):
    """Natural order (case_33 < case_100), matching the request file's own order."""
    prefix, _, num = case_id.rpartition("_")
    return (prefix, int(num)) if num.isdigit() else (case_id, 0)


def read_requests(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class Auditor:
    def __init__(self, dataset_dir: Path = DATASET_DIR, llm=None):
        t0 = time.perf_counter()
        self.dataset_dir = dataset_dir
        self.store = Store(dataset_dir)
        self.identity = IdentityGraph(dataset_dir)
        self.discovery = Discovery(self.store, self.identity)
        self.policy = Policy(dataset_dir)
        # LLM tier for texts the lexicon cannot place; cached, so offline reruns work.
        self.llm = llm if llm is not None else shared()
        self.intent = IntentGate(None if "rules_only_intent" in ABLATIONS else self.llm)
        # every participant-visible request competes for workflow-only resources
        self.world = (read_requests(dataset_dir / "sample_deletion_requests.csv")
                      + read_requests(dataset_dir / "deletion_requests.csv"))
        self.compile_seconds = time.perf_counter() - t0

    def _subjects(self, requests):
        subj = {}
        for i, q in enumerate(requests):
            if not self.intent.authorizes_deletion(q["request_text"]):
                continue
            uid = self.identity.resolve(q["email"], q["audit_at"])
            subj[(i, q["case_id"], q["email"])] = (uid, q["reported_at"], q["audit_at"])
        return subj

    def audit(self, requests: list[dict]) -> list[dict]:
        world = self.world + [q for q in requests if q not in self.world]
        subj = self._subjects(world)
        resolved = self.discovery.resolve_all(subj)
        index = {(q["case_id"], q["email"]): k for k in subj for q in [world[k[0]]]}
        out = []
        for q in requests:
            k = index.get((q["case_id"], q["email"]))
            if k is None:
                out.append(self._row(q, "NOT_APPLICABLE", [], {}))
                continue
            uid, _, audit_at = subj[k]
            out.append(self.decide(q, uid, resolved.get(k, {})))
        return sorted(out, key=lambda r: case_sort_key(r["case_id"]))

    def decide(self, q: dict, uid: str | None, cands: dict) -> dict:
        audit_at = q["audit_at"]
        keys = frozenset(self.identity.keys_at(uid, audit_at)) if uid else frozenset()
        items, later, absent_accounts = [], [], []
        for key, reasons in sorted(cands.items()):
            if key[0] is None or key[0] in EVIDENCE_ONLY_SYSTEMS or not RESOURCE_ID_RE.fullmatch(key[1]):
                continue
            st = reconstruct(self.store, key, audit_at, keys)
            t = self.policy.treatment(st)
            if t is None:
                continue
            until = st.attrs.get("retention_until", "")
            if t == RETAIN and until[:4].isdigit() and until < audit_at:
                t = DELETE                                   # retention period has lapsed
            violation, evidence = assess(st, t, audit_at)
            if relevant(st, t, violation, reasons):
                items.append(Item(st, t, violation, evidence, reasons))
            elif t == RETAIN and st.exists is not True and "identifier-later" in reasons:
                later.append(Item(st, t, False, "", reasons))
            elif t == DELETE and key[0] == "account_service" and st.exists is False and evidence:
                absent_accounts.append(Item(st, t, False, evidence, reasons))
        if absent_accounts and not any(i.state.system_id == "account_service" for i in items):
            # the subject's account is already gone: prove it, using the freshest proof
            items.append(max(absent_accounts, key=lambda i: (i.state.proof_time or "", i.state.resource_id)))
        status = "INCOMPLETE" if any(i.violation for i in items) else "COMPLETE"
        if status == "COMPLETE":
            # a COMPLETE verdict may only assert what evidence proves
            items = [i for i in items if i.evidence]
        if status == "INCOMPLETE":
            # A retained record first documented after audit_at cannot be cited, but the
            # post-remediation check must still confirm it was preserved.
            items += later
        conf = {}
        for it in items:
            p_state = state_confidence(it.state, it.treatment, it.violation, audit_at)
            p_link = link_confidence(it.reasons, self.discovery.link_prob.get((uid, (it.state.system_id, it.state.resource_id))))
            conf[(it.state.system_id, it.state.resource_id)] = (p_state * p_link, p_state, p_link)
        return self._row(q, status, build_steps(items, status), {"uid": uid, "items": items, "confidence": conf})

    @staticmethod
    def _row(q, status, steps, trace):
        return {"case_id": q["case_id"], "deletion_status": status, "steps": steps, "trace": trace}
