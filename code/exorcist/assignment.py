"""Optimal assignment of identifier-less workflow resources to people.

Problem: several deletion workflows act inside overlapping time windows, so a
resource whose identifiers are already gone (a deleted account, an anonymized
analytics profile) may plausibly belong to several subjects. Each resource belongs to
at most one person and each person has at most one such resource per system — a
bipartite matching. We solve it exactly with the Hungarian (Kuhn–Munkres) algorithm,
minimizing the total negative log-likelihood under the learned timing model:

    cost(person p, resource r) = λ·[r never directly observed]
                                 + min_actions −log N(offset; μ_sys, σ_sys)
    offset = (workflow action time on r) − (p's reported_at), in hours

Greedy "best pair first" can block a globally better matching; Hungarian cannot.
Each (system, connected component of the contest graph) is solved independently, so
matrices stay tiny. O(n²·m) per component, pure Python.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

INF = 1e18
UNSEEN_PENALTY = 50.0           # λ: prefer resources some evidence actually observed
MODEL_PATH = Path(__file__).resolve().parent / "timing_model.json"


class TimingModel:
    def __init__(self, path: Path = MODEL_PATH):
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.prior = data.get("_prior", {"mu": 0.0, "sigma": 1.0})
        self.params = {k: v for k, v in data.items() if not k.startswith("_")}

    def nll(self, system: str, offset_hours: float) -> float:
        from .config import ABLATIONS
        p = self.prior if "uniform_timing" in ABLATIONS else self.params.get(system, self.prior)
        z = (offset_hours - p["mu"]) / p["sigma"]
        return 0.5 * z * z + math.log(p["sigma"] * math.sqrt(2 * math.pi))


def hungarian(cost: list[list[float]]) -> list[int]:
    """Min-cost assignment for an n×m matrix (n ≤ m). Returns col index per row.
    Classic potentials formulation (Kuhn 1955 / Munkres 1957; Jonker–Volgenant style)."""
    n, m = len(cost), len(cost[0])
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [INF] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:                         # augment along the alternating path
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    out = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def optimal_matching(offers: dict[tuple, float]) -> dict:
    """offers: (person, resource) -> cost. Returns person -> resource for one system.
    Maximum-cardinality, then minimum-cost matching (unmatched rows use dummy columns
    priced above any real pair)."""
    # connected components over the bipartite contest graph (union-find)
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for person, res in offers:
        a, b = find(("p", person)), find(("r", res))
        if a != b:
            parent[a] = b
    comps: dict = {}
    for person, res in offers:
        comps.setdefault(find(("p", person)), set()).add((person, res))

    result = {}
    for pairs in comps.values():
        people = sorted({p for p, _ in pairs}, key=str)
        resources = sorted({r for _, r in pairs}, key=str)
        big = max(c for c in (offers[x] for x in pairs)) * 4 + 1e6   # "stay unmatched" price
        width = len(resources) + len(people)                          # + one dummy per person
        matrix = []
        for p in people:
            row = [offers.get((p, r), INF) for r in resources]
            row += [big] * len(people)
            matrix.append(row)
        for i, j in enumerate(hungarian(matrix) if width else []):
            if 0 <= j < len(resources) and matrix[i][j] < INF:
                result[people[i]] = resources[j]
    return result
