# Graph Report - hackerrank-orchestrate-october26  (2026-10-24)

## Corpus Check
- Corpus is ~14,614 words - fits in a single context window. You may not need a graph.

## Summary
- 176 nodes · 359 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 65% EXTRACTED · 35% INFERRED · 0% AMBIGUOUS · INFERRED: 125 edges (avg confidence: 0.89)
- Token cost: 107,321 input · 0 output

## Community Hubs (Navigation)
- Agent Rules & Logging
- Ingestion & Identity Discovery
- Contract & Policy Engine
- Design Doc & Open Questions
- Evaluation & Quality Gates
- Temporal State & Resurrection
- Provenance & Citation
- Time & Claims Principles
- Intent Gate & AI Edges

## God Nodes (most connected - your core abstractions)
1. `EXORCIST Design Document` - 27 edges
2. `EXORCIST Roadmap` - 19 edges
3. `Ghost Data Still Exists Problem Statement` - 17 edges
4. `EXORCIST System Journal` - 14 edges
5. `M0 Foundation and Understanding` - 12 edges
6. `Project Working Rules - EXORCIST (§10)` - 11 edges
7. `Evidence Loaders` - 11 edges
8. `Identity Graph (time-bounded union-find)` - 10 edges
9. `Temporal State Reconstructor` - 10 edges
10. `Custom Evaluation Cases C1-C8 (mutation generator)` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Canonical Ordering (phase, op rank, system_id, resource_id)` --semantically_similar_to--> `Single Canonical Sort Rule`  [INFERRED] [semantically similar]
  code/docs/design_doc.md → AGENTS.md
- `Rules Are Data (P6)` --semantically_similar_to--> `No Hardcoding Rule`  [INFERRED] [semantically similar]
  code/docs/design_doc.md → AGENTS.md
- `Byte-Identical Reruns (P7)` --semantically_similar_to--> `Determinism Rule (byte-identical output)`  [INFERRED] [semantically similar]
  code/docs/design_doc.md → AGENTS.md
- `Measure Before Believing (P8)` --semantically_similar_to--> `Regression Gate`  [INFERRED] [semantically similar]
  code/docs/design_doc.md → AGENTS.md
- `llm.py Provider Abstraction + Usage Logging` --implements--> `LLM Calls Only via llm.py`  [INFERRED]
  code/docs/design_doc.md → AGENTS.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **EXORCIST Per-Case Pipeline (Intent -> Identity -> State -> Policy -> Plan)** — code_docs_design_doc_intent_gate, code_docs_design_doc_loaders, code_docs_design_doc_observation_store, code_docs_design_doc_identity_graph, code_docs_design_doc_inverted_index, code_docs_design_doc_temporal_state_reconstructor, code_docs_design_doc_policy_engine, code_docs_design_doc_risk_graph_planner [EXTRACTED 1.00]
- **Challenge Contract Sources of Truth** — problem_statement_problem_statement, agents_project_contract, readme_readme_md, problem_statement_output_csv_contract, problem_statement_allowed_operations [INFERRED 0.85]
- **Custom Evaluation Fault-Injection Cases** — code_docs_design_doc_custom_case_c1, code_docs_design_doc_custom_case_c2, code_docs_design_doc_custom_case_c3, code_docs_design_doc_custom_case_c4, code_docs_design_doc_custom_case_c5, code_docs_design_doc_custom_case_c6, code_docs_design_doc_custom_case_c7, code_docs_design_doc_custom_case_c8 [EXTRACTED 1.00]

## Communities (11 total, 2 thin omitted)

### Community 0 - "Agent Rules & Logging"
Cohesion: 0.09
Nodes (25): Agent Trace Instructions, agent-trace.zip, Claude Code Session JSONL + /export, Challenge Rules, Dataset Development Rules, Knowledge Graph (graphify) Rule, Log Entry Format (SESSION START / per-turn), log.txt Shared Append-Only Log (+17 more)

### Community 1 - "Ingestion & Identity Discovery"
Cohesion: 0.13
Nodes (27): Activity CSV Loader (activity_claim, LINK_RESOURCE_IDENTITY), Aho-Corasick Automaton over All Identifiers, EXORCIST Pipeline Architecture, Cuckoo Filter Shard Pre-filter (scale-out), Evidence Corpus (94 files), Failure Modes and Mitigations, Identity Graph (time-bounded union-find), Inverted Index + Hash Postings (+19 more)

### Community 2 - "Contract & Policy Engine"
Cohesion: 0.11
Nodes (25): Dataset Contract, Deletion Decision Rules, Evaluable Submission Constraints, Project Contract (§6), Canonical Ordering (phase, op rank, system_id, resource_id), C3 Tombstone Holding email_hash, Policy Decision Table, EXORCIST Provenance-Graph Deletion Auditor (+17 more)

### Community 3 - "Design Doc & Open Questions"
Cohesion: 0.14
Nodes (22): Category Resolver, Code Layout (code/exorcist/), EXORCIST Design Document, End-to-End Per-Case Algorithm, Finding -> Remediation -> Verification 1:1 Mapping, Grading Contract Reverse-Engineered from Samples, Q1 Analytics DELETE vs ANONYMIZE (case_12), Q2 Support DELETE vs REDACT (+14 more)

### Community 4 - "Evaluation & Quality Gates"
Cohesion: 0.15
Nodes (9): Evaluation and Token Usage Reports, Ablation Studies, Evaluation Methodology, Output Invariant Checks, M6 Evaluation Workflow, Score Tracker, Results Table, evaluation_report.md Requirements (+1 more)

### Community 5 - "Temporal State & Resurrection"
Cohesion: 0.19
Nodes (14): Absence Proof Rule, C1 Historical Email Identity, C2 Resurrection via SYNC, C6 Audit Record Past retention_until, C7 Failover Replica Drift, C8 SUCCESS Claim Without Observation, Custom Evaluation Cases C1-C8 (mutation generator), Evidence-Strength Lattice (tiers 1-4) (+6 more)

### Community 6 - "Provenance & Citation"
Cohesion: 0.22
Nodes (8): Evidence Rules, Citation Selector, Evidence Citation Rule (latest direct observation <= audit_at), Explain Mode (--explain CASE), Latency and Cost Targets (<5 s warm, <$0.50 cold), Provenance Semirings (Green et al., PODS 2007), M7 Accuracy Push, M8 Polish and Demo

### Community 7 - "Time & Claims Principles"
Cohesion: 0.25
Nodes (6): Input and Time Contract (audit_at cutoff), C5 Evidence After audit_at, Design Principles P1-P8, GDPRbench (VLDB 2020), Lethe Delete-Aware LSM (SIGMOD 2020), reported_status Is a Claim

### Community 8 - "Intent Gate & AI Edges"
Cohesion: 0.31
Nodes (6): C4 Non-English Invoice Request (NOT_APPLICABLE), Intent Gate (cascade classifier), LLM Intent Tier (T2, JSON, temp 0), llm.py Provider Abstraction + Usage Logging, Multilingual Deletion Lexicon (T1), M4 Intent Gate

## Knowledge Gaps
- **19 isolated node(s):** `Evaluable Submission Constraints`, `Dataset Development Rules`, `agent-trace.zip`, `Claude Code Session JSONL + /export`, `ResourceState Data Contract` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 23 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `EXORCIST Design Document` connect `Design Doc & Open Questions` to `Agent Rules & Logging`, `Ingestion & Identity Discovery`, `Contract & Policy Engine`, `Evaluation & Quality Gates`, `Provenance & Citation`, `Time & Claims Principles`, `Intent Gate & AI Edges`?**
  _High betweenness centrality (0.304) - this node is a cross-community bridge._
- **What connects `Evaluable Submission Constraints`, `Dataset Development Rules`, `agent-trace.zip` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Agent Rules & Logging` be split into smaller, more focused modules?**
  _Cohesion score 0.0915915915915916 - nodes in this community are weakly interconnected._
- **Why does `EXORCIST Roadmap` connect `Agent Rules & Logging` to `Ingestion & Identity Discovery`, `Design Doc & Open Questions`, `Evaluation & Quality Gates`, `Temporal State & Resurrection`, `Provenance & Citation`, `Intent Gate & AI Edges`?**
  _High betweenness centrality (0.219) - this node is a cross-community bridge._
- **Should `Ingestion & Identity Discovery` be split into smaller, more focused modules?**
  _Cohesion score 0.12962962962962962 - nodes in this community are weakly interconnected._
- **Why does `Ghost Data Still Exists Problem Statement` connect `Contract & Policy Engine` to `Agent Rules & Logging`, `Evaluation & Quality Gates`, `Time & Claims Principles`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Should `Contract & Policy Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.11396011396011396 - nodes in this community are weakly interconnected._