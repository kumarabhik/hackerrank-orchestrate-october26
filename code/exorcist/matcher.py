"""Aho-Corasick multi-pattern matcher (Aho & Corasick, CACM 1975).

One automaton over every identifier of every user; one pass over each free-text
evidence body finds all mentions in O(N + M + z). Uses the C extension
`pyahocorasick` when installed, else this pure-Python implementation.
"""
from __future__ import annotations

from collections import deque


class AhoCorasick:
    def __init__(self, patterns):
        self.goto: list[dict] = [{}]
        self.fail: list[int] = [0]
        self.out: list[list] = [[]]
        for p in patterns:
            self._add(p)
        self._build()

    def _add(self, pattern: str):
        node = 0
        for ch in pattern:
            nxt = self.goto[node].get(ch)
            if nxt is None:
                nxt = len(self.goto)
                self.goto[node][ch] = nxt
                self.goto.append({})
                self.fail.append(0)
                self.out.append([])
            node = nxt
        self.out[node].append(pattern)

    def _build(self):
        q = deque(self.goto[0].values())
        while q:
            node = q.popleft()
            for ch, nxt in self.goto[node].items():
                q.append(nxt)
                f = self.fail[node]
                while f and ch not in self.goto[f]:
                    f = self.fail[f]
                self.fail[nxt] = self.goto[f].get(ch, 0) if self.goto[f].get(ch, 0) != nxt else 0
                self.out[nxt] = self.out[nxt] + self.out[self.fail[nxt]]

    def find_all(self, text: str):
        """Yield (end_index, pattern) for every occurrence."""
        node = 0
        for i, ch in enumerate(text):
            while node and ch not in self.goto[node]:
                node = self.fail[node]
            node = self.goto[node].get(ch, 0)
            for p in self.out[node]:
                yield i, p


def build(patterns):
    try:
        import ahocorasick  # type: ignore
    except ImportError:
        return AhoCorasick(patterns)
    a = ahocorasick.Automaton()
    for p in patterns:
        a.add_word(p, p)
    a.make_automaton()

    class _Wrap:
        def find_all(self, text):
            for end, p in a.iter(text):
                yield end, p
    return _Wrap()


def mentions(texts: dict[str, str], patterns) -> dict[str, set]:
    """evidence_id -> set of matched patterns (case-insensitive: patterns lowercased)."""
    auto = build({p.lower() for p in patterns if p})
    return {eid: {p for _, p in auto.find_all(t.lower())} for eid, t in texts.items()}
