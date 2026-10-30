# EXORCIST: Roadmap

Legend: `[ ]` not started · `[~]` partial / in progress · `[x]` completed

**Rules for this file** (see [AGENTS.md](AGENTS.md) §10):
- Update the box state the moment work starts or finishes.
- Every `[x]` must be backed by a passing check: a test, an eval number, or a file that exists.
- Add new tasks under the correct milestone instead of deleting old ones. Strike a dropped task through with `~~text~~` and give the reason.
- The **Current focus** line below must always name the single next task.

> **Current focus:** USER: create agent-trace.zip, upload code.zip + output.csv + log.txt (+ trace) on HackerRank (single submission — starts the 12 h AI-interview window), then rehearse with question.md.

**Score tracker** (latest sample-set numbers; full history in [system.md](system.md)):

| Metric | Value |
|---|---|
| Status accuracy (samples) | **100%** (32/32) |
| Step F1 / evidence acc / sequence acc | 93.3% / 99.5% / 56.2% (4-fold CV identical) |
| Exact-row match | 50.0% · custom cases 8/8 · reported_status baseline 53.1% |
| Full 518-row run | 0.64 s, 0 invariant violations, byte-identical reruns |
| Warm end-to-end | ≈0.3 s (compile ≈0.1 s, 0.32 ms/request) · confidence AUROC 0.946 |
| Full-run model usage | 16 cached responses, 33k tokens, ≈$0.011 (reruns $0) |

---

## M0: Foundation and understanding
- [x] Clone challenge repo, read `problem_statement.md`, `README.md`, `AGENTS.md`
- [x] Research prior art (US and China) and low-latency algorithms
- [x] Write detailed design doc ([design_doc.md](design_doc.md))
- [x] Reverse-engineer the grading contract from the 32 samples (design_doc §3)
- [x] Project rules in AGENTS.md §10; create roadmap.md, system.md, question.md, .gitignore
- [x] Knowledge graph of the project docs with graphify (`graphify-out/`)
- [x] Deep data exploration: every evidence file's shape and the meaning of every activity event type
- [x] Answer design_doc §14 open questions Q1–Q6 (Q1–Q4 in system.md; Q5 retention lapse → custom case C6; Q6 NOT_APPLICABLE → intent gate, cross-checked 10/10 with privacy-intake events) and record the answers in system.md
- [x] Choose LLM provider and set env var (user decision) — Groq via gitignored `.env`

## M1: Ingestion layer (deterministic)
- [x] `exorcist/config.py`: paths, operation ranks, phase ranks
- [x] SQL loader (`:memory:` per file, snapshot_scope times, replica tagging)
- [x] JSON loader (snapshot bundles, service exports, analytics report, export jobs/manifest, connector configs, security ledger)
- [x] Log loader (kv tokenizer; readback vs lookup-key lines; FOUND/NOT_FOUND)
- [x] TXT handover loader
- [x] PDF loader (`pypdf`, with VLM fallback hook)
- [x] Image loader (VLM → cached JSON; ids validated; 6/11 images also checked by eye)
- [x] Activity CSV loader (claims + LINK_RESOURCE_IDENTITY edges)
- [x] Observation Store with `by_resource`, `by_identifier`, `by_evidence` indexes
- [x] Coverage report: observations per file; 0-observation files flagged

## M2: Identity and discovery
- [x] Time-bounded union-find over identities + audit log
- [x] sha256(email) hash nodes; phone normalization
- [x] Ambiguity guard (no user↔user merge; time-scoped ownership)
- [x] Aho-Corasick automaton over all identifiers (pyahocorasick + pure-Python fallback)
- [x] Candidate-resource discovery per case (identifier links + workflow trace with global claim resolution; 100/111 gold resources, 3 are unobservable); unit tests on sample subjects

## M3: State, policy, plan (the scoring core)
- [x] Evidence-strength lattice + latest-strongest-wins reconstruction
- [x] Resurrection detection (delete → sync/restore → observed)
- [x] Replica drift evaluation
- [x] Category resolver (data-driven map) + rules loader (workflow action > explicit record_type > system default)
- [x] Decision table → finding / remediation / verification
- [x] Never-delete-retained guard + test
- [x] Canonical sort (phase, op rank, system, resource) + tests from samples
- [x] Citation selector (latest direct observation ≤ audit_at) + tie-break rule
- [x] Serializer + CSV writer (UTF-8, sorted, 518 rows)
- [x] `main.py` end-to-end: produces `output.csv`

## M4: Intent gate (AI edge #1)
- [x] Multilingual lexicon tier (deletion verbs + override intents)
- [x] LLM tier with JSON schema, temp 0, cache by text hash
- [x] Provider abstraction `llm.py` (groq / openai / xai / offline-cache) + usage logging
- [x] Review of all 398 unique texts: rules vs LLM audit 393/398, all 5 disagreements resolved (LLM errors) — system.md

## M5: Multimodal evidence (AI edge #2)
- [x] VLM extraction prompt + schema for dashboards
- [x] Run on 11 PNGs, cache, hand-verify (11/11 extracted; ids validated)
- [x] ~~PDF fallback path tested~~ — not needed: pypdf extracts all 4 PDFs (coverage report)

## M6: Evaluation workflow
- [x] `evaluation/main.py`: status acc, confusion matrix, step P/R/F1, field acc, sequence acc, exact match
- [x] Invariant checker over all 518 rows
- [x] Custom cases C1–C8 (mutation generator + expected outputs) — 8/8 pass
- [x] Ablation runner (history, claims, replicas, VLM, workflow link, scoped absence, intent tiers) + reported_status baseline
- [x] `evaluation_report.md` auto-generated + narrative: failures found and improvements made
- [x] `usage_report.md`: providers, models, calls, tokens in/out, totals, avg per request, cost

## M7: Accuracy push
- [x] Sample status accuracy = 100%
- [~] Sample exact-row match ≥ 90% — at 50%; remainder is the identical-reported_at ceiling + 3 unobservable resources
- [x] Error analysis on each mismatched sample, logged in system.md
- [x] Spot-audit 20 random test cases by hand with `--explain` (coherent; fixed 3 empty plans + legal leak found by the scan)

## M8: Polish and demo
- [x] `--explain CASE` provenance trace
- [x] Unit tests (`pytest code/tests`) green — 32 passed
- [x] Timing: warm full run < 5 s (measured: 0.56 s)
- [x] README.md in `code/` with setup + run + architecture summary
- [ ] ~~Optional: small HTML case viewer for the interview demo~~ — skipped; `--explain` covers the demo

## M9: Submission
- [x] Final clean run → root `output.csv` (518 rows, header exact, natural order, 0 invariant violations)
- [x] Final eval + usage reports regenerated from that run
- [x] `code.zip` packaged (78 files, 115 KB, secret scan clean; clean-extract offline rerun is byte-identical)
- [x] `log.txt` complete and valid (tool= / model= in every entry)
- [ ] Agent trace zip per `agent_trace_instructions.md`
- [ ] Upload to https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
- [ ] Rehearse with `question.md` before the AI Judge interview

## M10: Advanced math + latency (batch 6)
- [x] Profile the pipeline (cProfile): I/O, pypdf, image hashing, linear scope scans were the hot spots
- [x] Compile-once corpus cache keyed by SHA-256 fingerprint (scandir) — warm run ≈0.3 s
- [x] Lazy pypdf import; bisect over time-sorted capture index (O(log n) lookups)
- [x] Hungarian (Kuhn–Munkres) optimal assignment replaces greedy — verified vs brute force
- [x] Per-system Gaussian timing model with empirical-Bayes shrinkage (fit offline on public samples)
- [x] 4-fold cross-validation of the learned component (out-of-sample = in-sample)
- [x] Bayesian per-step confidence (log-odds evidence fusion × assignment posterior), AUROC 0.946
- [x] New ablations (greedy_assignment, uniform_timing), 7 new tests (39 total)
- [x] Docs: design_doc §16, README, reports regenerated; code.zip re-packed and re-verified offline
