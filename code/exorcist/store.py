"""Observation Store: the whole corpus compiled once into in-memory indexes.

by_resource   (system_id, resource_id) -> [Observation] sorted by observed_at
by_identifier typed identifier key     -> {(system_id, resource_id)}
by_evidence   evidence_id              -> [Observation]
scopes        system_id                -> [Scope] sorted by observed_at
"""
from __future__ import annotations

import hashlib
import os
import pickle
import time
from collections import defaultdict
from pathlib import Path

from .config import ABLATIONS, CACHE_DIR, DATASET_DIR
from .llm import shared
from .loaders import load_evidence, read_manifest

CODE_DIR = Path(__file__).resolve().parent


def _fingerprint(dataset_dir: Path) -> str:
    """Identity of a compiled corpus: every dataset file (path, size, mtime) + the source
    of every module that shapes observations + active ablations. Any change → recompile."""
    h = hashlib.sha256()

    def walk(d: str, rel: str):
        # os.scandir returns size/mtime with the directory listing (no per-file stat on Windows)
        with os.scandir(d) as it:
            entries = sorted(it, key=lambda e: e.name)
        for e in entries:
            if e.is_dir():
                walk(e.path, f"{rel}{e.name}/")
            else:
                st = e.stat()
                h.update(f"{rel}{e.name}|{st.st_size}|{st.st_mtime_ns}\n".encode())

    walk(str(dataset_dir), "")
    for p in sorted([*CODE_DIR.glob("*.py"), *(CODE_DIR / "loaders").glob("*.py")]):
        h.update(p.read_bytes())
    h.update(",".join(sorted(ABLATIONS)).encode())
    h.update(str(dataset_dir.resolve()).encode())
    return h.hexdigest()[:24]


def load_compiled(dataset_dir: Path):
    """Compile-once cache: a warm run unpickles the parsed corpus instead of re-reading
    94 files (SQL execution, PDF text extraction, log parsing, screenshot lookups)."""
    path = CACHE_DIR / "compiled" / f"store_{_fingerprint(dataset_dir)}.pkl"
    if path.exists():
        with path.open("rb") as fh:
            payload = pickle.load(fh)
        shared().used.extend(payload["llm_used"])      # keep usage accounting exact
        return payload["evidence"], True
    before = len(shared().used)
    evidence = load_evidence(dataset_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as fh:
        pickle.dump({"evidence": evidence, "llm_used": shared().used[before:]}, fh,
                    protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    return evidence, False


class Store:
    def __init__(self, dataset_dir: Path = DATASET_DIR):
        t0 = time.perf_counter()
        (self.observations, scope_list, self.texts,
         self.counts, self.skipped), self.cache_hit = load_compiled(dataset_dir)
        self.manifest = {r["file_id"]: r for r in read_manifest(dataset_dir)}
        self.file_time = {fid: r["captured_at"] for fid, r in self.manifest.items()}

        # Resolve document aliases (e.g. statement numbers) to catalogued resources.
        self.aliases = {o.attrs["alias"]: (o.system_id, o.resource_id)
                        for o in self.observations if "alias" in o.attrs}
        for o in self.observations:
            if o.system_id is None and o.resource_id in self.aliases:
                o.attrs["alias_of"] = o.resource_id
                o.system_id, o.resource_id = self.aliases[o.resource_id]

        self.by_resource: dict[tuple, list] = defaultdict(list)
        self.by_identifier: dict[str, set] = defaultdict(set)
        self.by_evidence: dict[str, list] = defaultdict(list)
        for o in self.observations:
            key = (o.system_id, o.resource_id)
            self.by_resource[key].append(o)
            self.by_evidence[o.evidence_id].append(o)
            for ref in o.refs:
                self.by_identifier[ref].add(key)
        for obs in self.by_resource.values():
            obs.sort(key=lambda o: (o.observed_at, o.evidence_id))

        self.scopes: dict[str, list] = defaultdict(list)
        for s in scope_list:
            self.scopes[s.system_id].append(s)
        for lst in self.scopes.values():
            lst.sort(key=lambda s: (s.observed_at, s.evidence_id))
        # parallel time keys so state reconstruction can bisect to the freshness window
        self.scope_times = {sys_id: [s.observed_at for s in lst] for sys_id, lst in self.scopes.items()}
        self.load_seconds = time.perf_counter() - t0

    def coverage_report(self) -> str:
        """Markdown table: observations per evidence file; zero-observation files flagged."""
        scope_counts: dict[str, int] = defaultdict(int)
        for lst in self.scopes.values():
            for s in lst:
                scope_counts[s.evidence_id] += 1
        lines = ["| file_id | path | observations | scopes | flag |", "|---|---|---|---|---|"]
        for fid, row in self.manifest.items():
            n, sc = self.counts.get(fid, 0), scope_counts.get(fid, 0)
            flag = ("VLM pending" if fid in self.skipped
                    else "scope-only (absence proof)" if n == 0 and sc
                    else "**ZERO**" if n == 0 else "")
            lines.append(f"| {fid} | {row['file_path']} | {n} | {sc} | {flag} |")
        lines.append(f"| activity | system_activity.csv | {self.counts.get('system_activity.csv', 0)} | 0 | |")
        total = len(self.observations)
        zero = [f for f, n in self.counts.items()
                if n == 0 and f not in self.skipped and not scope_counts.get(f)]
        summary = (f"\n**Total:** {total} observations, {len(self.by_resource)} resources, "
                   f"{len(self.by_identifier)} identifier keys, "
                   f"{sum(len(v) for v in self.scopes.values())} scopes, "
                   f"loaded in {self.load_seconds:.2f}s. "
                   f"Zero-observation parsed files: {zero or 'none'}. "
                   f"Images awaiting VLM: {len(self.skipped)}.")
        return "\n".join(lines) + "\n" + summary
