# Graph Report - hackerrank-orchestrate-october26  (2026-10-24)

## Corpus Check
- 40 files · ~32,961 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 2 file(s) not represented in the graph (top: (none) 2)

## Summary
- 446 nodes · 927 edges · 15 communities (13 shown, 2 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 65 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `acb3dfca`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Project Working Rules - EXORCIST (§10)
- test_core.py
- Ghost Data Still Exists Problem Statement
- json_.py
- auditor.py
- EXORCIST: Design Document
- Entries
- custom_cases.py
- test_loaders.py
- evaluation/main.py
- Evaluation Report — EXORCIST deletion auditor
- test_planner.py
- AhoCorasick
- LLM

## God Nodes (most connected - your core abstractions)
1. `Entries` - 28 edges
2. `make_obs()` - 25 edges
3. `Auditor` - 21 edges
4. `EXORCIST: Design Document` - 17 edges
5. `IdentityGraph` - 16 edges
6. `Store` - 16 edges
7. `Ghost Data Still Exists Problem Statement` - 16 edges
8. `Discovery` - 15 edges
9. `main()` - 14 edges
10. `reconstruct()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `10. Evaluation methodology` --references--> `email_hash()`  [INFERRED]
  design_doc.md → code/exorcist/ids.py
- `6.2 Observation Store` --references--> `Observation`  [INFERRED]
  design_doc.md → code/exorcist/model.py
- `6.1 Loaders` --references--> `Observation`  [INFERRED]
  design_doc.md → code/exorcist/model.py
- `6.1 Loaders` --references--> `table()`  [INFERRED]
  design_doc.md → code/evaluation/usage.py
- `How it works (one paragraph per stage)` --references--> `Observation`  [INFERRED]
  code/README.md → code/exorcist/model.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Challenge Contract Sources of Truth** — problem_statement_problem_statement, agents_project_contract, readme_readme_md, problem_statement_output_csv_contract, problem_statement_allowed_operations [INFERRED 0.85]

## Communities (15 total, 2 thin omitted)

### Community 0 - "Project Working Rules - EXORCIST (§10)"
Cohesion: 0.10
Nodes (8): Agent Trace Instructions, agent-trace.zip, Claude Code Session JSONL + /export, Challenge Rules, Knowledge Graph (graphify) Rule, Project Working Rules - EXORCIST (§10), question.md Interview Prep, Submission Checklist

### Community 1 - "test_core.py"
Cohesion: 0.06
Nodes (16): Discovery, _ts(), IdentityGraph, UnionFind, Policy, freshness_floor(), reconstruct(), visible() (+8 more)

### Community 2 - "Ghost Data Still Exists Problem Statement"
Cohesion: 0.06
Nodes (41): Dataset Contract, Dataset Development Rules, Deletion Decision Rules, Evaluable Submission Constraints, Evaluation and Token Usage Reports, Evidence Rules, Input and Time Contract (audit_at cutoff), Log Entry Format (SESSION START / per-turn) (+33 more)

### Community 3 - "json_.py"
Cohesion: 0.08
Nodes (25): canonical_system(), system_for_resource(), _key(), classify(), name_key(), load(), _bundle(), _flat() (+17 more)

### Community 4 - "auditor.py"
Cohesion: 0.08
Nodes (6): shared(), load(), load_evidence(), read_manifest(), extract_text(), load()

### Community 5 - "EXORCIST: Design Document"
Cohesion: 0.06
Nodes (33): cost(), table(), 10. Evaluation methodology, 11. Failure modes and mitigations, 12. Code layout, 13. Prior art (US and China) and our differentiation, 14. Open questions, 15. References (+25 more)

### Community 6 - "Entries"
Cohesion: 0.07
Nodes (30): [2026-10-24 14:10 UTC] DECISION Deterministic core, AI only at edges, [2026-10-24 14:10 UTC] DECISION Docs live in `code/docs/`, [2026-10-24 14:10 UTC] DISCOVERY Evidence corpus shapes, [2026-10-24 14:10 UTC] DISCOVERY Grading contract reverse-engineered from 32 samples, [2026-10-24 14:10 UTC] OPEN-QUESTION analytics DELETE vs ANONYMIZE (case_12), [2026-10-24 14:10 UTC] RESULT Environment, [2026-10-24 14:40 UTC] RESULT Knowledge graph built with graphify, [2026-10-24 14:55 UTC] ERROR Edited HackerRank's official AGENTS.md (+22 more)

### Community 7 - "custom_cases.py"
Cohesion: 0.17
Nodes (14): add_evidence(), c1_historical_email(), c2_resurrection(), c3_tombstone_with_identifier(), c4_non_english_non_deletion(), c5_evidence_after_audit(), c6_retention_lapsed(), c7_replica_drift() (+6 more)

### Community 8 - "test_loaders.py"
Cohesion: 0.11
Nodes (13): email_hash(), norm_email(), norm_phone(), obs(), store(), test_bundle_tombstone_and_empty_scope(), test_failover_replica_keeps_deleted_account(), test_identifier_normalization() (+5 more)

### Community 9 - "evaluation/main.py"
Cohesion: 0.11
Nodes (22): run_all(), How we evaluate, custom_markdown(), invariants(), levenshtein(), load_csv(), main(), metrics_markdown() (+14 more)

### Community 10 - "Evaluation Report — EXORCIST deletion auditor"
Cohesion: 0.10
Nodes (17): Ablation study, Additional evaluation cases created by the team, Custom evaluation cases (fault injection), Evaluation Report — EXORCIST deletion auditor, Failures found and improvements made, Known limitations (data-level ceilings), Results, Development-time model usage (not part of the final run) (+9 more)

### Community 11 - "test_planner.py"
Cohesion: 0.21
Nodes (13): classify_rules(), assess(), build_steps(), _ever(), Item, _latest(), relevant(), ResourceState (+5 more)

### Community 12 - "AhoCorasick"
Cohesion: 0.22
Nodes (4): AhoCorasick, build(), mentions(), test_aho_corasick_finds_overlapping_patterns()

## Knowledge Gaps
- **6 isolated node(s):** `agent-trace.zip`, `Claude Code Session JSONL + /export`, `Dataset Development Rules`, `Challenge Submission Link`, `Evaluable Submission Constraints` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 182 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `EXORCIST: Design Document` connect `EXORCIST: Design Document` to `Ghost Data Still Exists Problem Statement`?**
  _High betweenness centrality (0.413) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Auditor` (e.g. with `Discovery` and `IdentityGraph`) actually correct?**
  _`Auditor` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `agent-trace.zip`, `Claude Code Session JSONL + /export`, `Dataset Development Rules` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Project Working Rules - EXORCIST (§10)` be split into smaller, more focused modules?**
  _Cohesion score 0.09956709956709957 - nodes in this community are weakly interconnected._
- **Why does `email_hash()` connect `test_loaders.py` to `test_core.py`, `auditor.py`, `EXORCIST: Design Document`?**
  _High betweenness centrality (0.291) - this node is a cross-community bridge._
- **Should `test_core.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06397306397306397 - nodes in this community are weakly interconnected._
- **Why does `10. Evaluation methodology` connect `EXORCIST: Design Document` to `test_loaders.py`?**
  _High betweenness centrality (0.287) - this node is a cross-community bridge._