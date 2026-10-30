"""Identifier normalization and classification.

Every identifier is reduced to a typed key "kind:value" so that the same person
matches across formats (case-changed emails, differently formatted phones,
hash-only rows).
"""
from __future__ import annotations

import hashlib
import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
USER_RE = re.compile(r"^user_\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,}$")

DIRECT_PII_FIELDS = ("name", "email", "phone", "email_hash")


def norm_email(value: str) -> str:
    return value.strip().lower()


def norm_phone(value: str) -> str:
    return re.sub(r"\D", "", value)


def email_hash(email: str) -> str:
    return hashlib.sha256(norm_email(email).encode("utf-8")).hexdigest()


def classify(value) -> str | None:
    """Return a typed identifier key for a raw value, or None if it is not one."""
    if value is None or not isinstance(value, str):
        return None
    v = value.strip()
    if not v or v.lower() in {"null", "none", "no direct identifier"}:
        return None
    if USER_RE.match(v):
        return f"user:{v}"
    if HASH_RE.match(v.lower()):
        return f"hash:{v.lower()}"
    if EMAIL_RE.fullmatch(v):
        return f"email:{norm_email(v)}"
    if PHONE_RE.match(v) and len(norm_phone(v)) >= 7:
        return f"phone:{norm_phone(v)}"
    return None


def name_key(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return "name:" + " ".join(value.casefold().split())
