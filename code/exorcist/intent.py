"""Intent gate: does request_text authorize deletion? (design_doc §6.0)

Tier 1: multilingual lexicon. Override intents (access, copy, export, correction,
marketing opt-out, explicit "not a deletion", "keep my account") beat deletion
verbs, because non-deletion requests often mention deletion only to rule it out.
Tier 2: optional LLM for texts the lexicon cannot decide (see llm.py); without a
provider configured the gate falls back to the lexicon's best guess.
"""
from __future__ import annotations

import re

DELETION = re.compile("|".join([
    r"\bdelet", r"\beras", r"\bremove (?:my|the) (?:account|profile|personal)", r"\bclose (?:my|this|the) account",
    r"\bclosed\b", r"\bforget me", r"account[- ]deletion", r"\bdeletion\b",
    r"eliminaci[oó]n", r"\beliminar", r"\bborrar", r"suppression", r"\bsupprimer",
    r"l[oö]sch", r"exclus[aã]o", r"\bexcluir", r"\bapagar", r"cancellazione", r"\bcancellare",
    r"verwijder", r"usuni", r"удал", "删除", "削除", "삭제", "حذف",
]), re.I)

OVERRIDE = re.compile("|".join([
    r"not (?:asking|requesting) (?:for )?(?:deletion|erasure|to (?:delete|erase|close))",
    r"not a request to (?:erase|delete)", r"(?:don't|do not) (?:delete|close|erase|remove)",
    r"without removing", r"marketing lists? only", r"\bunsubscribe", r"stop (?:the )?(?:promotional|marketing)",
    r"\b(?:send|give) me a copy", r"\ba copy of", r"\bdownload my", r"portable format",
    r"what personal information you hold", r"information request",
    r"\bchange the email", r"\bcorrect it\b", r"\bmisspelled", r"replace it with the new",
    r"\bkeep the account", r"leave (?:the|my) (?:account|profile)", r"continue using",
    r"\bstill (?:use|need|want)", r"resetting the login", r"\bout of date",
]), re.I)


def classify_rules(text: str) -> tuple[bool | None, str]:
    """(authorizes_deletion or None if undecided, reason)."""
    t = " ".join((text or "").split())
    deletion = bool(DELETION.search(t))
    override = bool(OVERRIDE.search(t))
    if override:
        return False, "override-intent"
    if deletion:
        return True, "deletion-verb"
    return None, "no-signal"


class IntentGate:
    def __init__(self, llm=None):
        self.llm = llm
        self.decisions: dict[str, tuple] = {}

    def authorizes_deletion(self, text: str) -> bool:
        if text in self.decisions:
            return self.decisions[text][0]
        verdict, reason = classify_rules(text)
        if verdict is None and self.llm is not None:
            verdict, reason = self.llm.classify_intent(text), "llm"
        if verdict is None:
            # Requests arrive through the deletion channel; follow-ups like "remove that
            # search result" or "confirm the profile is gone" carry no classic verb.
            # Non-deletion requests in this channel state their override explicitly.
            verdict, reason = True, "default-deletion-channel"
        self.decisions[text] = (verdict, reason)
        return verdict
