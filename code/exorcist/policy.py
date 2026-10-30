"""Policy engine: deletion_rules.csv as data + category resolver (design_doc §6.6).

Required treatment of a resource, in priority order:
1. the treatment the deletion workflow itself attempted on it (its action type is
   the organization's classification; its reported result is only a claim),
2. an explicit record_type stated by evidence, looked up in deletion_rules.csv,
3. the system's default category, looked up in deletion_rules.csv.
Data flows and backups are processes, handled as FLOW / BACKUP.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .config import DATASET_DIR, SYSTEM_DEFAULT_RECORD_TYPE

DELETE, REDACT, ANONYMIZE, RETAIN, FLOW, BACKUP = (
    "DELETE", "REDACT", "ANONYMIZE", "RETAIN", "FLOW", "BACKUP")

WORKFLOW_ACTION_TREATMENT = {
    "DELETE_RECORD": DELETE, "REDACT_RECORD": REDACT, "ANONYMIZE_RECORD": ANONYMIZE,
    "RETAIN_RECORD": RETAIN, "DISABLE_DATA_FLOW": FLOW, "CHECK_DATA_FLOW": FLOW,
    "BLOCK_RESTORE": BACKUP, "CHECK_RESTORE_ACCESS": BACKUP,
}
PROCESS_CATEGORIES = {"DATA_FLOW": FLOW, "BACKUP_ARCHIVE": BACKUP}


def load_rules(dataset_dir: Path = DATASET_DIR) -> dict[str, dict]:
    with (dataset_dir / "deletion_rules.csv").open(encoding="utf-8", newline="") as fh:
        return {r["data_category"]: r for r in csv.DictReader(fh)}


class Policy:
    def __init__(self, dataset_dir: Path = DATASET_DIR):
        self.rules = load_rules(dataset_dir)

    def category(self, state) -> str | None:
        return state.record_type or SYSTEM_DEFAULT_RECORD_TYPE.get(state.system_id)

    def treatment(self, state) -> str | None:
        for et in reversed(state.workflow_actions):          # latest attempted action
            if t := WORKFLOW_ACTION_TREATMENT.get(et):
                if t in (FLOW, BACKUP) or state.system_id not in ("integration_service", "backup_service"):
                    return t
        cat = self.category(state)
        if cat in PROCESS_CATEGORIES:
            return PROCESS_CATEGORIES[cat]
        if cat in self.rules:
            return self.rules[cat]["required_action"]
        if state.system_id == "integration_service":
            return FLOW
        if state.system_id == "backup_service":
            return BACKUP
        return None
