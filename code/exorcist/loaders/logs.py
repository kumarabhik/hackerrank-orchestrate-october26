"""Log evidence in seven dialects, normalized to (ts, service, trace, event, fields),
then joined per trace: the identifier sits on *_started lines, the state on
*_completed lines."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import OBS_STATUSES, RESOURCE_ID_RE, canonical_system, system_for_resource
from ..model import READBACK, make_obs

KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
TS = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"
JSON_LINE = re.compile(TS + r"\s+(\{.*\})\s*$")
BRACKET = re.compile(TS + r"\s+\[(\w+)\]\s+\[([\w-]+)\]\s+\[([^\]]+)\]\s+(\w+):\s*(.*)$")
PIPE = re.compile(TS + r"\s+\|\s*(\w+)\s*\|\s*([\w-]+)\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|\s*(.*)$")
SYSLOG = re.compile(TS + r"\s+<\d+>1\s+\S+\s+([\w-]+)\s+(\S+)\s+-\s+-\s+(.*)$")
PLAIN = re.compile(TS + r"\s+(.*)$")

LOOKUP_KEYS = ("lookup_key", "match_key", "subject_key", "subject_ref", "query")
ABSENT_MARKERS = {("rows", "0"), ("http_status", "404"), ("result", "miss"),
                  ("total_hits", "0"), ("result", "NOT_FOUND")}


def _kv(text: str) -> dict:
    out = {}
    for k, v in KV_RE.findall(text):
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1].replace('\\"', '"')
        out[k] = v
    return out


def parse_line(line: str):
    """Return (ts, service, trace, event, fields) or None."""
    if m := JSON_LINE.match(line):
        d = json.loads(m.group(2))
        return m.group(1), d.get("service") or d.get("logger"), d.get("trace_id"), d.get("event"), d
    if m := BRACKET.match(line):
        f = _kv(m.group(6))
        return m.group(1), m.group(3), m.group(4), m.group(5), f
    if m := PIPE.match(line):
        f = _kv(m.group(6))
        return m.group(1), m.group(3), m.group(4), m.group(5), f
    if m := SYSLOG.match(line):
        f = _kv(m.group(4))
        return m.group(1), m.group(2), m.group(3), f.get("event"), f
    if m := PLAIN.match(line):
        f = _kv(m.group(2))
        if "message" in f and "=" in f["message"]:        # cloud-runtime escaped payload
            inner = _kv(f.pop("message"))
            f = {**f, **inner}
        service = f.get("service") or f.get("function")
        trace = f.get("trace_id") or f.get("requestId")
        return m.group(1), service, trace, f.get("event"), f
    return None


def _present(fields: dict) -> bool:
    return not any(str(fields.get(k)) == v for k, v in ABSENT_MARKERS)


def load(path: Path, evidence_id: str, manifest_time: str):
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed = [p for line in lines if (p := parse_line(line))]
    trace_keys: dict[str, set] = {}
    for ts, service, trace, event, f in parsed:
        if trace:
            for k in LOOKUP_KEYS:
                if f.get(k):
                    trace_keys.setdefault(trace, set()).add(f[k])

    observations = []
    for ts, service, trace, event, f in parsed:
        rid = f.get("resource_id")
        if not rid or not RESOURCE_ID_RE.fullmatch(rid):
            continue
        event = event or ""
        if event == "record_lookup" or ("record_type" in f and "result" in f):
            result = f.get("result")
            observations.append(make_obs(
                evidence_id, ts, rid, {}, system_id=f.get("system"), source_kind=READBACK,
                source=event, present=result != "NOT_FOUND",
                status=result if result in OBS_STATUSES else None,
                record_type=f.get("record_type"), extra_refs=(f.get("subject_reference"),)))
            continue
        if event.endswith("_started") or event in ("connection_acquired", "cache_lookup"):
            continue
        system = canonical_system(service)
        if system_for_resource(rid) and system != system_for_resource(rid):
            system = system_for_resource(rid)
        keys = trace_keys.get(trace, set()) if trace else set()
        observations.append(make_obs(
            evidence_id, ts, rid, f, system_id=system, source_kind=READBACK,
            source=event, present=_present(f), extra_refs=tuple(keys)))
    return observations, [], "\n".join(lines)
