"""Calibrated confidence for every emitted step (does not change decisions).

State belief — naive-Bayes evidence fusion in log-odds space:

    logit P(state) = logit(π) + Σ_i  s_i · w_i · log( r_i / (1 − r_i) )

  r_i  reliability of observation i's source kind (snapshot > readback > document >
       screenshot read by a VLM > absence inferred from a scoped capture)
  s_i  +1 if observation i supports the asserted state, −1 if it contradicts it
  w_i  exponential age decay 2^(−age/half_life): older captures say less about *now*

Link belief — how sure we are the resource belongs to this subject:
  identifier link → near-certain; workflow-only link → softmax over every competing
  claimant's timing likelihood, P(p | r) = exp(−c_p) / Σ_q exp(−c_q).

Step confidence = P(state) · P(link).
"""
from __future__ import annotations

import math
from datetime import datetime

RELIABILITY = {"snapshot": 0.97, "readback": 0.95, "document": 0.93, "screenshot": 0.90, "scope": 0.85}
PRIOR = 0.5
HALF_LIFE_DAYS = 7.0
IDENTIFIER_LINK = 0.995


def _days(a: str, b: str) -> float:
    pa = datetime.fromisoformat(a.replace("Z", "+00:00"))
    pb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return max((pb - pa).total_seconds() / 86400, 0.0)


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def state_confidence(state, treatment: str, violation: bool, audit_at: str) -> float:
    """P(the asserted current state is true | visible evidence)."""
    lo = _logit(PRIOR)
    asserted_present = bool(state.exists) if treatment in ("DELETE", "RETAIN") else None
    for o in state.observations:
        if o.source_kind == "activity":
            continue
        r = RELIABILITY.get(o.source_kind, 0.9)
        w = 0.5 ** (_days(o.observed_at, audit_at) / HALF_LIFE_DAYS)
        if asserted_present is not None:
            if o.present is None:
                continue
            s = 1 if o.present == asserted_present else -1
        elif treatment in ("REDACT", "ANONYMIZE"):
            if o.status is None:
                continue
            s = 1 if (o.status == "IDENTIFIABLE") == violation else -1
        else:                                   # FLOW / BACKUP: process status
            if o.status not in ("ACTIVE", "DISABLED", "BLOCKED"):
                continue
            s = 1 if (o.status == "ACTIVE") == violation else -1
        lo += s * w * _logit(r)
    if asserted_present is False and state.proof and state.proof.startswith("evidence_"):
        if not any(o.evidence_id == state.proof for o in state.observations):
            lo += 0.5 ** (_days(state.proof_time or audit_at, audit_at) / HALF_LIFE_DAYS) * _logit(RELIABILITY["scope"])
    return 1 / (1 + math.exp(-lo))


def link_confidence(reasons: set, link_prob: float | None) -> float:
    if reasons & {"identifier", "identifier-later"}:
        return IDENTIFIER_LINK
    return link_prob if link_prob is not None else 0.5
