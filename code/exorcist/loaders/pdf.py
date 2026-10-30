"""PDF business documents (pypdf text). Each document becomes observations for every
resource it names, linked to every identifier it contains. Register-style rows
('ORD-… | user_NN | … | Retain until …') become legal-hold records."""
from __future__ import annotations

import re
from pathlib import Path

from ..config import DOC_REF_RE, RESOURCE_ID_RE
from ..ids import EMAIL_RE
from ..model import DOCUMENT, make_obs

USER_RE = re.compile(r"\buser_\d+\b")
PHONE_RE = re.compile(r"\+\d[\d ()-]{7,}\d")
RETAIN_RE = re.compile(r"retain until\s+(\d{1,2} \w{3} \d{4})", re.I)
REGISTER_ROW = re.compile(r"^(ORD-\d+)\s*\|\s*(user_\d+)\s*\|(.*)$", re.M)
SUBJECT_LINE = re.compile(r"^Detail\n(?!.*@)(?!.*\d)([A-Z][\w'-]+(?: [A-Z][\w'-]+)+)$", re.M)


def extract_text(path: Path) -> str:
    from pypdf import PdfReader          # lazy: only paid on a compile-cache miss
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def load(path: Path, evidence_id: str, manifest_time: str):
    text = extract_text(path)
    observations = []

    for order, user, rest in REGISTER_ROW.findall(text):
        attrs = {"user_ref": user}
        if m := RETAIN_RE.search(rest):
            attrs["retention_until"] = m.group(1)
        obs = make_obs(evidence_id, manifest_time, order, {"customer_reference": user,
                       **({"retention_until": attrs["retention_until"]} if "retention_until" in attrs else {})},
                       system_id="legal_service", source_kind=DOCUMENT, source=path.stem,
                       record_type="LEGAL_HOLD_RECORD")
        observations.append(obs)

    resources = sorted(set(RESOURCE_ID_RE.findall(text)))
    if not resources and not REGISTER_ROW.search(text):
        # no native id: emit the document's business reference; the store resolves it
        # to a resource through catalog aliases (LINK_RESOURCE_IDENTITY).
        resources = sorted(set(DOC_REF_RE.findall(text)))
    if resources:
        record = {}
        if emails := EMAIL_RE.findall(text):
            record["email"] = emails[0]
        if phones := PHONE_RE.findall(text):
            record["phone"] = phones[0]
        if users := USER_RE.findall(text):
            record["customer_reference"] = users[0]
        if m := SUBJECT_LINE.search(text):
            record["full_name"] = m.group(1)
        if m := RETAIN_RE.search(text):
            record["retention_until"] = m.group(1)
        # A document that describes itself as an attachment is the attachment itself.
        rtype = "SUPPORT_ATTACHMENT" if "attachment" in text.lower() else None
        for rid in resources:
            observations.append(make_obs(evidence_id, manifest_time, rid, record,
                                         source_kind=DOCUMENT, source=path.stem,
                                         record_type=rtype))
    return observations, [], text
