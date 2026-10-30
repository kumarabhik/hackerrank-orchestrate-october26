"""Time-bounded identity graph.

Union-find (path compression + union by rank) over typed identifier keys and user
nodes. Guard: two different users are never merged; an identifier that would bridge
two users is recorded as ambiguous and owned per point in time instead.

keys_at(user, t) reconstructs exactly the identifiers the user had up to time t by
replaying user_audit_log backwards from the current snapshot.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .config import ABLATIONS, DATASET_DIR
from .ids import classify, email_hash, name_key

FIELDS = ("name", "email", "phone", "email_hash")


class UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        self.rank.setdefault(x, 0)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:                    # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> str:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return ra


def _key(field: str, value: str | None) -> str | None:
    if not value:
        return None
    return name_key(value) if field == "name" else classify(value)


class IdentityGraph:
    def __init__(self, dataset_dir: Path = DATASET_DIR):
        with (dataset_dir / "user_identities.csv").open(encoding="utf-8", newline="") as fh:
            self.users = {r["user_id"]: r for r in csv.DictReader(fh)}
        self.audit: dict[str, list] = defaultdict(list)
        with (dataset_dir / "user_audit_log.csv").open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                self.audit[r["user_id"]].append(r)
        for rows in self.audit.values():
            rows.sort(key=lambda r: r["event_time"])

        # All-time ownership via guarded union-find.
        self.uf = UnionFind()
        self.ambiguous: set[str] = set()
        self.key_users: dict[str, set] = defaultdict(set)
        for uid in self.users:
            for k in self._all_time_keys(uid):
                self.key_users[k].add(uid)
        for k, owners in self.key_users.items():
            if len(owners) > 1:
                self.ambiguous.add(k)                    # never bridge two users
                continue
            self.uf.union("user:" + next(iter(owners)), k)

    # -- key reconstruction --------------------------------------------------
    def _all_time_keys(self, uid: str) -> set[str]:
        keys = {"user:" + uid}
        row = self.users[uid]
        for f in FIELDS:
            if k := _key(f, row.get(f)):
                keys.add(k)
        for a in self.audit.get(uid, []):
            for v in (a["old_value"], a["new_value"]):
                if k := _key(a["field_name"], v):
                    keys.add(k)
        return self._with_hashes(keys)

    @staticmethod
    def _with_hashes(keys: set[str]) -> set[str]:
        for k in list(keys):
            if k.startswith("email:"):
                keys.add("hash:" + email_hash(k[6:]))
        return keys

    def values_at(self, uid: str, at: str) -> dict[str, set]:
        """Field -> every value the user had at or before `at` (current + historical)."""
        cur = {f: self.users[uid].get(f) for f in FIELDS}
        hist: dict[str, set] = defaultdict(set)
        for a in reversed(self.audit.get(uid, [])):      # undo changes made after `at`
            if a["event_time"] > at and cur.get(a["field_name"]) == a["new_value"]:
                cur[a["field_name"]] = a["old_value"]
        for a in ([] if "no_history" in ABLATIONS else self.audit.get(uid, [])):
            if a["event_time"] <= at:
                hist[a["field_name"]].update({a["old_value"], a["new_value"]})
        for f, v in cur.items():
            if v:
                hist[f].add(v)
        return hist

    def keys_at(self, uid: str, at: str, with_names: bool = False) -> set[str]:
        keys = {"user:" + uid}
        for f, vals in self.values_at(uid, at).items():
            if f == "name" and not with_names:
                continue
            for v in vals:
                if k := _key(f, v):
                    keys.add(k)
        return self._with_hashes(keys)

    # -- resolution ------------------------------------------------------------
    def resolve(self, email: str, at: str) -> str | None:
        """User who owned this email at time `at` (current or historical)."""
        k = classify(email)
        if not k:
            return None
        cands = [u for u in self.key_users.get(k, ()) if k in self.keys_at(u, at)]
        if len(cands) == 1:
            return cands[0]
        if not cands:
            return None
        # shared identifier: prefer the user holding it as current value at `at`
        cur = [u for u in cands
               if any(_key(f, self.users[u].get(f)) == k for f in FIELDS)]
        return sorted(cur or cands)[0]

    def owners(self, keys) -> set[str]:
        """Users unambiguously identified by any of the given (non-name) keys."""
        out = set()
        for k in keys:
            if k.startswith("name:") or k in self.ambiguous:
                continue
            root = self.uf.find(k)
            if root.startswith("user:"):
                out.add(root[5:])
            elif k in self.key_users:
                out.update(self.key_users[k])
        return out
