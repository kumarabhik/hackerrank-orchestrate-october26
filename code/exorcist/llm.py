"""LLM / VLM access: one place for provider calls, caching and usage accounting.

Provider: any OpenAI-compatible chat endpoint (default Groq). Keys come only from
the environment or the uncommitted repo-root .env file.

Every call is cached by sha256(model + messages) under code/cache/llm/, so a rerun
makes zero network calls and is byte-identical. Every *network* call appends one
line to code/cache/usage.jsonl (model, purpose, tokens, latency) which feeds
evaluation/usage_report.md.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import CACHE_DIR, REPO_ROOT

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "xai": ("https://api.x.ai/v1", "XAI_API_KEY"),
}
DEFAULT_TEXT_MODEL = "openai/gpt-oss-20b"
DEFAULT_VISION_MODEL = "qwen/qwen3.8-27b"
# USD per 1M tokens (input, output) for the usage report; override via env if prices change.
PRICES = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "qwen/qwen3.8-27b": (0.29, 0.59),
}


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class LLM:
    def __init__(self, provider: str | None = None, offline: bool = False):
        load_dotenv()
        self.provider = provider or os.environ.get("EXORCIST_LLM_PROVIDER", "groq")
        self.base_url, key_var = PROVIDERS[self.provider]
        self.key = os.environ.get(key_var, "")
        self.text_model = os.environ.get("EXORCIST_TEXT_MODEL", DEFAULT_TEXT_MODEL)
        self.vision_model = os.environ.get("EXORCIST_VISION_MODEL", DEFAULT_VISION_MODEL)
        self.offline = offline or not self.key        # cache-only mode
        self.cache_dir = CACHE_DIR / "llm"
        self.usage_path = CACHE_DIR / "usage.jsonl"
        self.calls = {"network": 0, "cache": 0}
        self.used: list[dict] = []      # every model response this process relied on

    # -- core -----------------------------------------------------------------
    @staticmethod
    def _digest(model: str, messages: list) -> str:
        return hashlib.sha256(json.dumps([model, messages], sort_keys=True).encode()).hexdigest()

    def chat(self, messages: list, model: str, purpose: str, max_tokens: int = 800,
             json_mode: bool = True) -> str | None:
        digest = self._digest(model, messages)
        cached = self.cache_dir / f"{digest}.json"
        if cached.exists():
            self.calls["cache"] += 1
            entry = json.loads(cached.read_text(encoding="utf-8"))
            self.used.append(entry)
            return entry["content"]
        if self.offline:
            return None
        body = {"model": model, "messages": messages, "temperature": 0, "seed": 7,
                "max_completion_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                     "User-Agent": "exorcist/1.0"})
        t0 = time.perf_counter()
        for attempt in range(8):
            try:
                resp = json.load(urllib.request.urlopen(req, timeout=120))
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")
                if e.code in (429, 500, 502, 503) and attempt < 7:
                    # free-tier rate limits: honour "try again in 12.3s" when given
                    m = re.search(r"try again in ([\d.]+)(ms|s)", detail)
                    wait = (float(m.group(1)) / (1000 if m.group(2) == "ms" else 1) + 1) if m else 2 ** attempt * 3
                    time.sleep(min(wait, 65))
                    continue
                raise RuntimeError(f"{self.provider} HTTP {e.code}: {detail[:200]}") from None
        content = resp["choices"][0]["message"]["content"]
        usage = resp.get("usage", {})
        self.calls["network"] += 1
        self.used.append({"model": model, "purpose": purpose, "usage": usage})
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"model": model, "purpose": purpose, "content": content,
                                      "usage": usage}, ensure_ascii=False, indent=1), encoding="utf-8")
        with self.usage_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "provider": self.provider, "model": model, "purpose": purpose,
                                 "prompt_tokens": usage.get("prompt_tokens", 0),
                                 "completion_tokens": usage.get("completion_tokens", 0),
                                 "latency_s": round(time.perf_counter() - t0, 3)}) + "\n")
        return content

    @staticmethod
    def parse_json(text: str | None):
        if not text:
            return None
        t = text.strip()
        if t.startswith("```"):
            t = t.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            start, end = t.find("{"), t.rfind("}")
            return json.loads(t[start:end + 1]) if start >= 0 < end else None

    # -- tasks ----------------------------------------------------------------
    def classify_intent(self, text: str) -> bool | None:
        msg = [{"role": "system", "content": INTENT_PROMPT},
               {"role": "user", "content": text}]
        out = self.parse_json(self.chat(msg, self.text_model, "intent", max_tokens=300))
        if not isinstance(out, dict) or "authorizes_deletion" not in out:
            return None
        return bool(out["authorizes_deletion"])

    def classify_intents_batch(self, texts: list[str]) -> dict[str, bool]:
        """Audit helper: many texts per call (cheap); returns text -> authorizes_deletion."""
        numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(texts))
        msg = [{"role": "system", "content": INTENT_PROMPT.split("Reply with JSON only")[0] +
                'Reply with JSON only: {"results": [{"i": <number>, "authorizes_deletion": true|false}]}'},
               {"role": "user", "content": numbered}]
        out = self.parse_json(self.chat(msg, self.text_model, "intent-audit", max_tokens=4000)) or {}
        res = {}
        for r in out.get("results", []):
            if isinstance(r, dict) and isinstance(r.get("i"), int) and 0 <= r["i"] < len(texts):
                res[texts[r["i"]]] = bool(r.get("authorizes_deletion"))
        return res

    def extract_screenshot(self, path: Path) -> dict | None:
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        msg = [{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]
        return self.parse_json(self.chat(msg, self.vision_model, f"vision:{path.name}", max_tokens=2500))


_SHARED: LLM | None = None


def shared() -> LLM:
    """Process-wide client so usage accounting sees every response a run relies on."""
    global _SHARED
    if _SHARED is None:
        _SHARED = LLM()
    return _SHARED


INTENT_PROMPT = """You classify customer privacy requests for an e-commerce company.
Decide whether the request AUTHORIZES DELETION of the person's account or personal data
(erasure, account closure, removing their records, or following up on/confirming such a
deletion). IMPORTANT: asking you to verify, audit, check or confirm that their account or
data was deleted/removed/is gone, or to remove what remains, IS a deletion request (the
person wants the deletion completed and proven). Requests ONLY for access/copy/export of
data, correction/update of details,
marketing opt-out, login help, or that explicitly say they are not asking for deletion,
do NOT authorize deletion. The text may be in any language.
Reply with JSON only: {"authorizes_deletion": true|false, "intent": "<deletion|access|export|correction|marketing_opt_out|other>", "language": "<iso code>"}"""

VISION_PROMPT = """This is a screenshot of an internal admin tool at an online shop.
Extract every fact about specific customer data records. Copy identifiers EXACTLY as
shown (resource ids like account_5762, support_9538, data_flow_1121, backup_123,
audit_record_003, search_42, analytics_7, export_9, tombstone_5, user ids like user_11,
emails, phone numbers). Never invent or complete an identifier you cannot read.

Return JSON only:
{"screen": "<tool and page name>",
 "as_of": "<date/time shown on the page, or null>",
 "subject": {"user_id": null|str, "name": null|str, "email": null|str, "phone": null|str},
 "records": [
   {"resource_id": "<exact id or null>", "system": "<owning service if shown, else null>",
    "user_id": null|str, "name": null|str, "email": null|str, "phone": null|str,
    "email_hash": null|str,
    "status": "<status text shown, e.g. Active, Deleted, Healthy, Restorable, Blocked, Anonymized>",
    "enabled": null|true|false,           // for syncs/connectors: is it running/continuous?
    "restore_allowed": null|true|false,   // for backups/archives: can it still be restored?
    "contains_personal_data": null|true|false,
    "detail": "<short free text>"}]}
Include one entry per resource id visible anywhere on the page (tables, side panels,
breadcrumbs, activity feeds). If the page is about one customer, also add an entry for
their primary record."""
