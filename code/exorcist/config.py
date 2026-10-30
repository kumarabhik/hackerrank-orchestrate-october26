"""Paths, contract vocabulary and canonical ranks.

Everything here comes from problem_statement.md; nothing is case-specific.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "dataset"
EVIDENCE_DIR = DATASET_DIR
OUTPUT_CSV = REPO_ROOT / "output.csv"
CACHE_DIR = REPO_ROOT / "code" / "cache"

# --- Contract: phases and operations, in the order of the problem statement table.
PHASES = ("FINDING", "REMEDIATION", "VERIFICATION")
PHASE_RANK = {p: i for i, p in enumerate(PHASES)}

# operation -> (phase, state); dict order == canonical operation rank
OPERATIONS: dict[str, tuple[str, str]] = {
    "REPORT_REMAINING_RECORD": ("FINDING", "PRESENT"),
    "REPORT_EXPOSED_PII": ("FINDING", "PRESENT"),
    "REPORT_ACTIVE_DATA_FLOW": ("FINDING", "ACTIVE"),
    "REPORT_RESTORE_RISK": ("FINDING", "ACTIVE"),
    "DISABLE_DATA_FLOW": ("REMEDIATION", "DISABLED"),
    "BLOCK_RESTORE": ("REMEDIATION", "BLOCKED"),
    "DELETE_RECORD": ("REMEDIATION", "ABSENT"),
    "REDACT_RECORD": ("REMEDIATION", "REDACTED"),
    "ANONYMIZE_RECORD": ("REMEDIATION", "ANONYMIZED"),
    "VERIFY_RECORD_ABSENT": ("VERIFICATION", "ABSENT"),
    "VERIFY_RECORD_PRESENT": ("VERIFICATION", "PRESENT"),
    "VERIFY_RECORD_REDACTED": ("VERIFICATION", "REDACTED"),
    "VERIFY_RECORD_ANONYMIZED": ("VERIFICATION", "ANONYMIZED"),
    "VERIFY_DATA_FLOW_DISABLED": ("VERIFICATION", "DISABLED"),
    "VERIFY_RESTORE_BLOCKED": ("VERIFICATION", "BLOCKED"),
}
OPERATION_RANK = {op: i for i, op in enumerate(OPERATIONS)}

STATUSES = ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")

# Ablation switches for the evaluation report (empty in production). Each disables one
# component so its contribution can be measured: no_history, trust_claims, no_replicas,
# no_vlm, no_workflow_link, no_scoped_absence, rules_only_intent.
ABLATIONS: set[str] = set()

# --- Normalized observation status vocabulary (what a piece of evidence saw).
FOUND, NOT_FOUND = "FOUND", "NOT_FOUND"
IDENTIFIABLE, ANONYMIZED, REDACTED = "IDENTIFIABLE", "ANONYMIZED", "REDACTED"
ACTIVE, DISABLED, BLOCKED = "ACTIVE", "DISABLED", "BLOCKED"
OBS_STATUSES = {FOUND, NOT_FOUND, IDENTIFIABLE, ANONYMIZED, REDACTED, ACTIVE, DISABLED, BLOCKED}

# --- System vocabulary. Resource-id prefix -> owning system (observed in the samples).
RESOURCE_PREFIX_SYSTEM = {
    "account_": "account_service",
    "search_": "search_service",
    "support_": "support_platform",
    "analytics_": "analytics_platform",
    "export_": "export_service",
    "data_flow_": "integration_service",
    "backup_": "backup_service",
    "audit_record_": "security_service",
    "tombstone_": "identity_service",
    "object_": "object_storage",
    "marketing_": "marketing_platform",
}
RESOURCE_ID_RE = re.compile(
    r"\b(?:account|search|support|analytics|export|data_flow|backup|audit_record|tombstone|object|marketing)_\d+\b"
)

# Service/logger names seen in logs that alias a canonical system.
SERVICE_ALIASES = {
    "profile_service": "account_service",
    "support_replica": "support_platform",
    "search_index_service": "search_service",
}

# Default record_type (policy data_category) per system, used when evidence
# does not state it explicitly. Support/analytics refinements live in policy.
SYSTEM_DEFAULT_RECORD_TYPE = {
    "account_service": "USER_PROFILE",
    "search_service": "SEARCH_INDEX_ENTRY",
    "support_platform": "SUPPORT_MESSAGE",
    "analytics_platform": "ANALYTICS_PROFILE",
    "export_service": "USER_EXPORT",
    "integration_service": "DATA_FLOW",
    "backup_service": "BACKUP_ARCHIVE",
    "security_service": "SECURITY_AUDIT_LOG",
    "identity_service": "ACCOUNT_TOMBSTONE",
    "legal_service": "LEGAL_HOLD_RECORD",
    "object_storage": "SUPPORT_ATTACHMENT",
    "marketing_platform": "MARKETING_PROFILE",
}

# Flat inventory tables (customer_data_inventory_*.sql) -> system.
INVENTORY_TABLE_SYSTEM = {
    "customer_profiles": "account_service",
    "customer_search_documents": "search_service",
    "customer_analytics_profiles": "analytics_platform",
    "support_records": "support_platform",
    "customer_exports": "export_service",
    "connector_subscriptions": "integration_service",
    "backup_restore_entries": "backup_service",
    "security_audit_records": "security_service",
    "customer_profiles_primary": "account_service",
    "customer_profiles_failover_replica": "account_service",
    "search_documents_primary": "search_service",
}


# Business document references (statements, attachments) resolved via catalog aliases.
DOC_REF_RE = re.compile(r"\b[A-Z]{2,4}-\d{4}-\d{4}-\d{4}\b|\b[\w-]+\.pdf\b")


def system_for_resource(resource_id: str | None) -> str | None:
    if not resource_id:
        return None
    for prefix, system in RESOURCE_PREFIX_SYSTEM.items():
        if resource_id.startswith(prefix):
            return system
    return None


def canonical_system(name: str | None) -> str | None:
    if not name:
        return None
    return SERVICE_ALIASES.get(name, name)
