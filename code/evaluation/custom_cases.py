"""Custom evaluation cases C1–C8 (mutation-based, design_doc §10).

Each case copies the participant dataset to a temporary directory, injects exactly
one controlled fault around a public sample case that the system already answers
exactly, runs the full auditor on that dataset, and compares with an expected
answer derived by hand from the contract and deletion_rules.csv.
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
from pathlib import Path

from exorcist.auditor import Auditor
from exorcist.config import DATASET_DIR
from exorcist.planner import STEP_KEYS


def S(phase, system, rid, op, state, ev=""):
    return dict(zip(STEP_KEYS[1:], (phase, system, rid, op, state, ev)))


def number(steps):
    return [{"step_no": i, **s} for i, s in enumerate(steps, 1)]


def sample_request(case_id):
    with (DATASET_DIR / "sample_deletion_requests.csv").open(encoding="utf-8", newline="") as fh:
        return dict(next(r for r in csv.DictReader(fh) if r["case_id"] == case_id))


def add_evidence(d: Path, rel: str, content: str, captured_at: str) -> str:
    (d / rel).write_text(content, encoding="utf-8")
    with (d / "evidence_files.csv").open(encoding="utf-8", newline="") as fh:
        n = sum(1 for _ in csv.DictReader(fh)) + 1
    fid = f"evidence_{n:02d}"
    with (d / "evidence_files.csv").open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow([fid, rel, "custom_eval_mutation", captured_at])
    return fid


def record_export(t, rows):
    return json.dumps({"exported_at": t, "origin": "custom_eval", "record_count": len(rows),
                       "records": [dict(zip(("recorded_at", "system", "resource_id", "record_type",
                                                 "result", "subject_reference"), r)) for r in rows]})


# Expected outputs of the unmodified base cases (identical to sample_output.csv).
BASE_01 = [S("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", "evidence_54")]
BASE_21_VER = [("account_service", "account_6440", "VERIFY_RECORD_ABSENT", "ABSENT"),
               ("security_service", "audit_record_3737", "VERIFY_RECORD_PRESENT", "PRESENT"),
               ("analytics_platform", "analytics_5335", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED")]


def c1_historical_email(d: Path):
    """Request arrives under the subject's OLD email (changed before the request)."""
    with (d / "user_audit_log.csv").open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(["audit_9001", "user_01", "2025-11-02T10:00:00Z", "email",
                                 "amina.em.old@gmail.com", "amina.elmasri@gmail.com"])
    q = sample_request("case_01") | {"case_id": "custom_C1", "email": "amina.em.old@gmail.com"}
    return q, "COMPLETE", number(BASE_01)


def c2_resurrection(d: Path):
    """A sync re-creates the deleted profile after the workflow's successful delete."""
    with (d / "system_activity.csv").open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(["activity_9001", "2026-08-25T03:00:00Z", "SYNC_RECORD", "account_service",
                                 "account_replication_cluster", "account_001", "SUCCESS",
                                 "Replication worker reported its final checkpoint for account_001."])
    fid = add_evidence(d, "evidence/records/custom_resurrection_check.json", record_export(
        "2026-09-03T00:00:00Z", [("2026-09-03T00:00:00Z", "account_service", "account_001", "USER_PROFILE",
                                  "FOUND", "amina.elmasri@gmail.com")]), "2026-09-03T00:00:00Z")
    q = sample_request("case_01") | {"case_id": "custom_C2"}
    return q, "INCOMPLETE", number([
        S("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", fid),
        S("REMEDIATION", "account_service", "account_001", "DELETE_RECORD", "ABSENT"),
        S("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT")])


def c3_tombstone_with_identifier(d: Path):
    """An account tombstone still exposes a direct identifier (must keep only user_id)."""
    fid = add_evidence(d, "evidence/records/custom_tombstone_check.json", record_export(
        "2026-09-15T11:00:00Z", [("2026-09-15T11:00:00Z", "identity_service", "tombstone_9901",
                                  "ACCOUNT_TOMBSTONE", "IDENTIFIABLE", "user_21")]), "2026-09-15T11:00:00Z")
    q = sample_request("case_21") | {"case_id": "custom_C3"}
    ver = BASE_21_VER[:2] + [("identity_service", "tombstone_9901", "VERIFY_RECORD_REDACTED", "REDACTED")] + BASE_21_VER[2:]
    return q, "INCOMPLETE", number([
        S("FINDING", "identity_service", "tombstone_9901", "REPORT_EXPOSED_PII", "PRESENT", fid),
        S("REMEDIATION", "identity_service", "tombstone_9901", "REDACT_RECORD", "REDACTED"),
        *[S("VERIFICATION", *v) for v in ver]])


def c4_non_english_non_deletion(d: Path):
    """A Spanish invoice-copy request that explicitly keeps the account."""
    q = sample_request("case_01") | {"case_id": "custom_C4", "request_text":
        "Quiero una copia de mis facturas del año pasado. No borren nada, sigo usando la cuenta."}
    return q, "NOT_APPLICABLE", []


def c5_evidence_after_audit(d: Path):
    """Evidence of a remaining record captured AFTER audit_at must not change the answer."""
    add_evidence(d, "evidence/records/custom_late_check.json", record_export(
        "2026-09-04T09:00:00Z", [("2026-09-04T09:00:00Z", "account_service", "account_001", "USER_PROFILE",
                                  "FOUND", "amina.elmasri@gmail.com")]), "2026-09-04T09:00:00Z")
    q = sample_request("case_01") | {"case_id": "custom_C5"}
    return q, "COMPLETE", number(BASE_01)


def c6_retention_lapsed(d: Path):
    """A security audit record whose supplied retention period ended before audit_at."""
    p = d / "evidence/records/service_resource_export_20260915_114455.json"
    p.write_text(p.read_text(encoding="utf-8").replace(
        '"resource_id": "audit_record_3737",\n          "retention_until": "2034-09-30T23:59:59Z"',
        '"resource_id": "audit_record_3737",\n          "retention_until": "2026-09-01T00:00:00Z"'), encoding="utf-8")
    q = sample_request("case_21") | {"case_id": "custom_C6"}
    return q, "INCOMPLETE", number([
        S("FINDING", "security_service", "audit_record_3737", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_92"),
        S("REMEDIATION", "security_service", "audit_record_3737", "DELETE_RECORD", "ABSENT"),
        S("VERIFICATION", "account_service", "account_6440", "VERIFY_RECORD_ABSENT", "ABSENT"),
        S("VERIFICATION", "security_service", "audit_record_3737", "VERIFY_RECORD_ABSENT", "ABSENT"),
        S("VERIFICATION", "analytics_platform", "analytics_5335", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED")])


def c7_replica_drift(d: Path):
    """The primary no longer holds the profile but a read replica still does."""
    rec = json.dumps({"resource_id": "account_001", "user_id": "user_01", "full_name": "Amina El-Masri",
                      "email": "amina.elmasri@gmail.com", "account_status": "ACTIVE"})
    sql = ("-- Captured at: 2026-09-03T00:00:00Z\nBEGIN TRANSACTION;\n"
           "CREATE TABLE customer_data_primary (resource_id TEXT PRIMARY KEY, origin_system TEXT NOT NULL, "
           "collection_name TEXT NOT NULL, record_json TEXT NOT NULL, updated_at TEXT NOT NULL);\n"
           "CREATE TABLE customer_data_read_replica (resource_id TEXT PRIMARY KEY, origin_system TEXT NOT NULL, "
           "collection_name TEXT NOT NULL, record_json TEXT NOT NULL, updated_at TEXT NOT NULL);\nCOMMIT;\n"
           "INSERT INTO customer_data_primary VALUES('account_8801','account_service','customer_profiles',"
           "'{\"resource_id\":\"account_8801\",\"email\":\"someone.else@example.com\"}','2026-09-03T00:00:00Z');\n"
           f"INSERT INTO customer_data_read_replica VALUES('account_001','account_service','customer_profiles','{rec}','2026-09-03T00:00:00Z');\n")
    fid = add_evidence(d, "evidence/databases/custom_read_replica_20260903.sql", sql, "2026-09-03T00:00:00Z")
    q = sample_request("case_01") | {"case_id": "custom_C7"}
    return q, "INCOMPLETE", number([
        S("FINDING", "account_service", "account_001", "REPORT_REMAINING_RECORD", "PRESENT", fid),
        S("REMEDIATION", "account_service", "account_001", "DELETE_RECORD", "ABSENT"),
        S("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT")])


def c8_success_claim_without_proof(d: Path):
    """A 'DISABLE_DATA_FLOW SUCCESS' claim, but later evidence still shows the flow active."""
    with (d / "system_activity.csv").open("a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(["activity_9002", "2026-09-10T08:00:00Z", "DISABLE_DATA_FLOW", "deletion_worker",
                                 "integration_service", "data_flow_9846", "SUCCESS",
                                 "Policy action completed for data_flow_9846."])
    q = sample_request("case_15") | {"case_id": "custom_C8"}
    with (DATASET_DIR / "sample_output.csv").open(encoding="utf-8", newline="") as fh:
        gold = next(r for r in csv.DictReader(fh) if r["case_id"] == "case_15")
    return q, gold["deletion_status"], json.loads(gold["steps_json"])


CASES = [c1_historical_email, c2_resurrection, c3_tombstone_with_identifier, c4_non_english_non_deletion,
         c5_evidence_after_audit, c6_retention_lapsed, c7_replica_drift, c8_success_claim_without_proof]


def run_all():
    results = []
    for fn in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "dataset"
            shutil.copytree(DATASET_DIR, d)
            q, want_status, want_steps = fn(d)
            row = Auditor(d).audit([q])[0]
            ok_status = row["deletion_status"] == want_status
            ok_steps = row["steps"] == want_steps
            results.append({"case": fn.__name__, "doc": fn.__doc__.strip(), "status_ok": ok_status,
                            "steps_ok": ok_steps, "want": (want_status, want_steps),
                            "got": (row["deletion_status"], row["steps"])})
    return results
