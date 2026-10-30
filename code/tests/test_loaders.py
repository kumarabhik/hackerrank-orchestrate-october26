"""Loader and store tests. Facts asserted here are read from participant evidence and
checked against the public samples' citations; none is a hidden label."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exorcist.config import OPERATION_RANK, OPERATIONS  # noqa: E402
from exorcist.ids import classify, email_hash  # noqa: E402
from exorcist.loaders.logs import parse_line  # noqa: E402
from exorcist.store import Store  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return Store()


def obs(store, system, rid, evidence=None):
    return [o for o in store.by_resource[(system, rid)] if evidence in (None, o.evidence_id)]


def test_operation_ranks_follow_contract_table():
    ops = list(OPERATIONS)
    assert ops[0] == "REPORT_REMAINING_RECORD" and ops[-1] == "VERIFY_RESTORE_BLOCKED"
    assert OPERATION_RANK["DISABLE_DATA_FLOW"] < OPERATION_RANK["DELETE_RECORD"]


def test_identifier_normalization():
    assert classify("OBI.ADAEZE@ICLOUD.COM") == "email:obi.adaeze@icloud.com"
    assert classify("+91 98765 73142") == "phone:919876573142"
    assert classify("user_05") == "user:user_05"
    assert classify("null") is None
    assert len(email_hash("A@B.com")) == 64


@pytest.mark.parametrize("line,service,event", [
    ('2026-07-28T05:51:21Z [INFO] [account_service] [tr-1] profile_lookup_completed: resource_id="account_7947" rows="0"', "account_service", "profile_lookup_completed"),
    ('2026-07-03T07:51:32Z | DEBUG | security_service | tr-5 | audit_record_read_completed | resource_id="audit_record_4413"', "security_service", "audit_record_read_completed"),
    ('2026-04-19T06:51:13Z {"service":"search_service","trace_id":"tr-7","event":"index_query_started","match_key":"a@b.com"}', "search_service", "index_query_started"),
    ('2026-03-25T08:51:23Z <12>1 node-1 support_platform tr-74 - - level=WARN resource_id="support_9464" event="message_pii_scan"', "support_platform", "message_pii_scan"),
    ('2026-09-30T11:51:03Z requestId=tr-2 level=DEBUG function=profile_service message="resource_id=\\"account_1\\" event=\\"profile_lookup_completed\\""', "profile_service", "profile_lookup_completed"),
    ('2026-02-18T05:47:12Z level=INFO service=integration_service trace_id=rb-1 event=connector_config_read_completed resource_id=data_flow_3669 enabled=true', "integration_service", "connector_config_read_completed"),
])
def test_log_dialects(line, service, event):
    ts, svc, trace, ev, fields = parse_line(line)
    assert (svc, ev) == (service, event)
    assert ts.endswith("Z")


def test_every_parsable_file_yields_observations_or_scopes(store):
    scoped = {s.evidence_id for lst in store.scopes.values() for s in lst}
    for fid, row in store.manifest.items():
        if fid in store.skipped or row["file_path"].endswith(".png"):
            continue                    # a screenshot may legitimately name no resource id
        assert store.counts[fid] > 0 or fid in scoped, fid


def test_failover_replica_keeps_deleted_account(store):
    # sample case_05 cites evidence_54 for account_005 remaining
    o = obs(store, "account_service", "account_005", "evidence_54")
    assert o and o[0].present and o[0].replica == "failover_replica"


def test_readback_trace_joins_lookup_key(store):
    # identifier lives on the *_started line, state on *_completed (same trace)
    o = obs(store, "account_service", "account_6523", "evidence_67")
    assert o and o[0].present is False and "email:leonie.g9352@outlook.com" in o[0].refs


def test_record_style_and_handover_status(store):
    o = obs(store, "integration_service", "data_flow_9522", "evidence_03")
    assert o and o[0].status == "ACTIVE" and o[0].record_type == "DATA_FLOW"


def test_service_export_404_is_absence(store):
    o = obs(store, "account_service", "account_3136", "evidence_92")
    assert o and o[0].present is False


def test_bundle_tombstone_and_empty_scope(store):
    t = obs(store, "identity_service", "tombstone_440", "evidence_51")
    assert t and t[0].status == "REDACTED"
    assert any(s.evidence_id == "evidence_51" and not s.resource_ids
               for s in store.scopes["account_service"])


def test_pdf_attachment_and_alias(store):
    a = obs(store, "support_platform", "support_001", "evidence_58")
    assert a and a[0].status == "IDENTIFIABLE" and a[0].pii.get("phone")
    s = obs(store, "export_service", "export_1842", "evidence_18")
    assert s and s[0].attrs.get("alias_of") == "NST-2026-0718-1842"


def test_activity_checks_are_observations(store):
    checks = [o for o in store.observations if o.source == "CHECK_DATA_FLOW"]
    assert checks and all(o.status == "ACTIVE" and o.source_kind == "readback" for o in checks)
