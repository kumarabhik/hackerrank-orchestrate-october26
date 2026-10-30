"""Identity, matcher, discovery, state and policy tests (batch 2)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exorcist.discovery import Discovery  # noqa: E402
from exorcist.identity import IdentityGraph, UnionFind  # noqa: E402
from exorcist.matcher import AhoCorasick  # noqa: E402
from exorcist.policy import Policy  # noqa: E402
from exorcist.state import reconstruct  # noqa: E402
from exorcist.store import Store  # noqa: E402


@pytest.fixture(scope="module")
def env():
    s = Store()
    ig = IdentityGraph()
    return s, ig, Discovery(s, ig), Policy()


def test_union_find_path_compression():
    uf = UnionFind()
    uf.union("a", "b"); uf.union("b", "c"); uf.union("d", "c")
    assert len({uf.find(x) for x in "abcd"}) == 1


def test_aho_corasick_finds_overlapping_patterns():
    ac = AhoCorasick(["he", "she", "his", "hers"])
    assert sorted(p for _, p in ac.find_all("ushers")) == ["he", "hers", "she"]


def test_resolve_current_and_historical(env):
    s, ig, _, _ = env
    assert ig.resolve("amina.elmasri@gmail.com", "2026-09-03T11:30:00Z") == "user_01"
    hist = next((u, a) for u, rows in ig.audit.items() for a in rows if a["field_name"] == "email")
    uid, row = hist
    assert ig.resolve(row["old_value"], row["event_time"]) == uid      # old email still resolves


def test_keys_at_respects_time(env):
    _, ig, _, _ = env
    uid, rows = next((u, r) for u, r in ig.audit.items() if any(a["field_name"] == "email" for a in r))
    change = next(a for a in rows if a["field_name"] == "email")
    before = ig.keys_at(uid, "2000-01-01T00:00:00Z")
    assert f"email:{change['new_value'].lower()}" not in before        # future value invisible


def test_users_never_merged(env):
    _, ig, _, _ = env
    for k in ig.ambiguous:
        assert not ig.uf.find(k).startswith("user:") or len(ig.key_users[k]) == 1


def test_discovery_identifier_and_replica(env):
    s, ig, d, _ = env
    uid = ig.resolve("diya.k4436@outlook.com", "2026-09-21T10:00:00Z")
    c = d.candidates(uid, "2026-09-18T12:00:00Z", "2026-09-21T10:00:00Z")
    assert ("search_service", "search_1007") in c                   # nested document PII


def test_state_failover_replica_drift(env):
    s, ig, _, pol = env
    st = reconstruct(s, ("account_service", "account_005"), "2026-09-08T00:00:00Z")
    assert st.exists and st.replicas["failover_replica"][0] and pol.treatment(st) == "DELETE"


def test_state_ignores_evidence_filed_after_audit(env):
    s, _, _, _ = env
    st = reconstruct(s, ("support_platform", "support_5281"), "2026-09-15T12:00:00Z")
    assert st.status == "IDENTIFIABLE"                              # evidence_02 filed 09-17 ignored


def test_workflow_action_sets_treatment(env):
    s, _, _, pol = env
    st = reconstruct(s, ("analytics_platform", "analytics_9914"), "2026-09-16T00:00:00Z")
    assert pol.treatment(st) == "DELETE"


def test_backup_status_from_restore_flag(env):
    s, _, _, pol = env
    st = reconstruct(s, ("backup_service", "backup_4978"), "2026-09-16T12:00:00Z")
    assert pol.treatment(st) == "BACKUP" and st.status == "ACTIVE"


def test_retain_never_delete(env):
    s, _, _, pol = env
    st = reconstruct(s, ("security_service", "audit_record_3737"), "2026-09-15T12:00:00Z")
    assert pol.treatment(st) == "RETAIN" and st.exists
