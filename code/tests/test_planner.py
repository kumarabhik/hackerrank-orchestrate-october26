"""Planner, intent gate and end-to-end contract tests (batch 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exorcist.auditor import case_sort_key  # noqa: E402
from exorcist.intent import classify_rules  # noqa: E402
from exorcist.planner import Item, build_steps  # noqa: E402
from exorcist.policy import BACKUP, DELETE, FLOW, REDACT, RETAIN  # noqa: E402
from exorcist.state import ResourceState  # noqa: E402


def item(system, rid, t, violation, ev="evidence_x"):
    return Item(ResourceState(system, rid), t, violation, ev, {"identifier"})


def test_canonical_order_matches_contract_example():
    # mirrors sample case_11's shape: flow disabled before records are touched
    items = [item("search_service", "search_052", DELETE, True),
             item("support_platform", "support_864", REDACT, True),
             item("integration_service", "data_flow_9522", FLOW, True),
             item("account_service", "account_4248", DELETE, False),
             item("security_service", "audit_record_9394", RETAIN, False)]
    steps = build_steps(items, "INCOMPLETE")
    ops = [s["operation"] for s in steps]
    assert ops[:3] == ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW"]
    assert ops[3] == "DISABLE_DATA_FLOW"                      # cut the pipe first
    assert [s["resource_id"] for s in steps if s["phase"] == "VERIFICATION"][:3] == \
        ["account_4248", "search_052", "audit_record_9394"]
    assert [s["step_no"] for s in steps] == list(range(1, len(steps) + 1))
    assert all(s["evidence_id"] == "" for s in steps if s["phase"] != "FINDING")


def test_retained_records_never_deleted():
    steps = build_steps([item("security_service", "audit_record_1", RETAIN, False)], "COMPLETE")
    assert [s["operation"] for s in steps] == ["VERIFY_RECORD_PRESENT"]


def test_complete_cases_only_verify_with_evidence():
    steps = build_steps([item("backup_service", "backup_1", BACKUP, False, "evidence_9")], "COMPLETE")
    assert steps == [{"step_no": 1, "phase": "VERIFICATION", "system_id": "backup_service",
                      "resource_id": "backup_1", "operation": "VERIFY_RESTORE_BLOCKED",
                      "state": "BLOCKED", "evidence_id": "evidence_9"}]


def test_intent_gate_overrides_and_languages():
    assert classify_rules("Please stop the promotional emails. I still need the account, "
                          "so I am not asking for deletion.")[0] is False
    assert classify_rules("Can you correct it without removing any of my records?")[0] is False
    assert classify_rules("Solicito la eliminación permanente de la cuenta.")[0] is True
    assert classify_rules("이 이메일 주소에 연결된 계정의 영구 삭제를 요청합니다.")[0] is True
    assert classify_rules("Please erase the account linked to this email address.")[0] is True


def test_natural_case_order():
    assert sorted(["case_100", "case_33", "case_9"], key=case_sort_key) == ["case_9", "case_33", "case_100"]
