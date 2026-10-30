"""Tests for the optimization and probability components (batch 6)."""
import itertools
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exorcist.assignment import TimingModel, hungarian, optimal_matching  # noqa: E402
from exorcist.confidence import link_confidence, state_confidence  # noqa: E402
from exorcist.model import Observation  # noqa: E402
from exorcist.state import ResourceState  # noqa: E402


def test_hungarian_matches_brute_force():
    rng = random.Random(0)
    for _ in range(200):
        n = rng.randint(1, 5)
        m = [[rng.randint(0, 30) for _ in range(n)] for _ in range(n)]
        h = hungarian(m)
        best = min(sum(m[i][p[i]] for i in range(n)) for p in itertools.permutations(range(n)))
        assert sum(m[i][h[i]] for i in range(n)) == best


def test_optimal_matching_beats_greedy():
    # greedy takes a->r1 (cost 1) and strands b; optimal is a->r2, b->r1
    offers = {("a", "r1"): 1.0, ("a", "r2"): 5.0, ("b", "r1"): 2.0}
    assert optimal_matching(offers) == {"a": "r2", "b": "r1"}


def test_matching_respects_one_to_one():
    offers = {(p, r): float(abs(i - j)) for i, p in enumerate("abc") for j, r in enumerate(["x", "y"])}
    m = optimal_matching(offers)
    assert len(set(m.values())) == len(m) <= 2


def test_timing_model_prefers_system_specific_offsets():
    tm = TimingModel()
    # accounts are acted on before the report, search entries after it
    assert tm.nll("account_service", -0.7) < tm.nll("account_service", +1.0)
    assert tm.nll("search_service", +0.8) < tm.nll("search_service", -0.7)


def _obs(present, status, kind, t):
    return Observation("evidence_x", t, "account_service", "account_1", kind, present=present, status=status)


def test_confidence_grows_with_agreeing_fresh_evidence():
    audit = "2026-09-15T12:00:00Z"
    one = ResourceState("account_service", "account_1", exists=True,
                        observations=[_obs(True, "FOUND", "snapshot", "2026-09-15T10:00:00Z")])
    two = ResourceState("account_service", "account_1", exists=True,
                        observations=one.observations + [_obs(True, "FOUND", "readback", "2026-09-15T11:00:00Z")])
    stale = ResourceState("account_service", "account_1", exists=True,
                          observations=[_obs(True, "FOUND", "snapshot", "2026-08-20T10:00:00Z")])
    c1, c2, cs = (state_confidence(s, "DELETE", True, audit) for s in (one, two, stale))
    assert 0.5 < cs < c1 < c2 < 1


def test_conflicting_evidence_lowers_confidence():
    audit = "2026-09-15T12:00:00Z"
    st = ResourceState("account_service", "account_1", exists=True,
                       observations=[_obs(True, "FOUND", "snapshot", "2026-09-15T10:00:00Z"),
                                     _obs(False, "NOT_FOUND", "readback", "2026-09-14T10:00:00Z")])
    assert state_confidence(st, "DELETE", True, audit) < 0.7


def test_link_confidence():
    assert link_confidence({"identifier"}, None) > 0.99
    assert math.isclose(link_confidence({"workflow"}, 0.4), 0.4)
