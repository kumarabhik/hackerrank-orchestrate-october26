# EXORCIST: System Journal

This is the project's memory of **important results, errors, and how they were solved**. It is append-only: correct earlier entries by adding a new one that references them. See [AGENTS.md](AGENTS.md) §10 for when to write here.

Entry format:
```
### [YYYY-MM-DD HH:MM UTC] <TYPE> <short title>
TYPE ∈ RESULT | ERROR | DECISION | DISCOVERY | OPEN-QUESTION
- What happened:
- Evidence / numbers:
- Root cause (for ERROR):
- Fix / decision:
- Follow-up:
```

---

## Results table (one row per evaluation run)

| Date (UTC) | Commit/desc | Status acc | Step F1 | Exact rows | Seq acc | Runtime | Notes |
|---|---|---|---|---|---|---|---|
| 2026-10-24 18:05 | batch 3 first end-to-end | 84.4% | 81.1% | 31.2% | 31.2% | 0.39 s | intent gate too strict, workflow extras |
| 2026-10-24 18:25 | intent default + later-retained + 1:1 workflow | **100%** | **90.7%** | 46.9% | 46.9% | 0.37 s | remaining = timing ties + 3 unobservable |
| 2026-10-24 19:40 | + screenshots (VLM) + LLM intent tier + per-person workflow claims | **100%** | **92.0%** | 50.0% | 50.0% | 0.41 s | custom 8/8; full run 0.56 s, 0 invariants |
| 2026-10-25 02:30 | + Hungarian assignment + shrunk Gaussian timing NLL + confidence + compile cache | **100%** | **93.3%** | 56.2% | 56.2% | 0.30 s | 4-fold CV identical; AUROC 0.946; custom 8/8 |

---

## Entries

### [2026-10-24 14:10 UTC] DISCOVERY Grading contract reverse-engineered from 32 samples
- What happened: dumped all 32 sample outputs, with cited evidence resolved to file paths.
- Evidence / numbers:
  - Operation counts: VERIFY_ABSENT 50, VERIFY_PRESENT 24, REMAINING 21, DELETE 21, VERIFY_ANONYMIZED 12, EXPOSED_PII 11, VERIFY_REDACTED 10, VERIFY_FLOW_DISABLED 9, VERIFY_RESTORE_BLOCKED 6, ACTIVE_FLOW 6, DISABLE 6, REDACT 6, ANONYMIZE 5, RESTORE_RISK 3, BLOCK 3.
  - Top cited files: evidence_92 (36), evidence_94 (9), evidence_03 (7), evidence_01 (5), evidence_54/05/51 (4 each).
- Fix / decision: adopted these rules (design_doc §3):
  1. Sort steps by (phase, op rank in table order, system_id, resource_id).
  2. Verification covers every relevant resource's end state, not only remediated ones.
  3. Each finding maps to exactly one remediation and one verification.
  4. Citations are the latest direct observation ≤ audit_at; for INCOMPLETE cases, future steps get `""`.
  5. `reported_status` is uncorrelated with the truth (case_25: NOT_STARTED → COMPLETE).
- Follow-up: open questions Q1–Q6 in design_doc §14.

### [2026-10-24 14:10 UTC] DISCOVERY Evidence corpus shapes
- SQL inventories share one schema with `snapshot_scope(origin_system, captured_at)`. Replica captures use separate `*_primary` / `*_replica` tables.
- JSON bundles: `snapshots[].{captured_at, data_store, collection, records[]}`.
- Readback logs are `key=value`. Inside a trace, `*_read_started lookup_key=` links an identifier to a resource, and `*_read_completed` carries the state.
- Screenshots contain citable facts. Example: connector console 2026-08-07 shows `data_flow_1121`, selector `jain.aditi@gmail.com`, Continuous; `data_flow_9846` belongs to `lucia-torres@gmail.com` (sample case_15's flow).
- 375 unique request texts across 518 requests. reported_status: 254 COMPLETE / 152 PARTIAL / 112 NOT_STARTED.

### [2026-10-24 14:10 UTC] OPEN-QUESTION analytics DELETE vs ANONYMIZE (case_12)
- `analytics_9914` is REMAINING_RECORD → DELETE_RECORD instead of ANONYMIZE. This needs a record-level inspection of evidence_01 (service_events_ap_south_20260915.log). Tracked as design_doc §14 Q1.

### [2026-10-24 14:10 UTC] DECISION Deterministic core, AI only at edges
- Reason: the grader does exact structured matching and ordering, so LLM variance would directly cost points. Models are used only for intent (multilingual) and screenshot/PDF reading, are cached, and run at temperature 0.

### [2026-10-24 14:10 UTC] DECISION Docs live in `code/docs/`
- Reason: `code.zip` = `README.md` + `code/`, so the AI Judge sees these docs. `question.md` stays at the repo root and is gitignored (personal interview prep, not part of the submission).
- `code/DESIGN.md` (first draft) was superseded by `design_doc.md` and removed.

### [2026-10-24 14:10 UTC] RESULT Environment
- Windows 11, Python 3.11 (`C:\Users\kumar\AppData\Local\Programs\Python\Python311`), Git Bash + PowerShell, graphify CLI installed. Use `encoding='utf-8'` and `newline=''` for every CSV read and write.

### [2026-10-24 14:40 UTC] RESULT Knowledge graph built with graphify
- What happened: ran `/graphify .` with `.graphifyignore` excluding `dataset/`, `graphify-out/`, `log.txt`; `question.md` excluded automatically via `.gitignore`.
- Evidence / numbers: 10 files (2 code, 8 docs, ~14.6k words) → 176 nodes, 359 edges, 11 communities, 3 hyperedges. Health check: 0 dangling/missing edges; 4 reciprocal edge pairs collapse in undirected view (harmless). Extraction cost ≈107k subagent tokens (in/out split not reported).
- Communities: Agent Rules & Logging · Ingestion & Identity Discovery · Contract & Policy Engine · Design Doc & Open Questions · Evaluation & Quality Gates · Temporal State & Resurrection · Provenance & Citation · Time & Claims Principles · Intent Gate & AI Edges · (2 entry-point singletons).
- Follow-up: the graph flagged 19 weakly-connected nodes (submission constraints, dataset-development rules, agent-trace) — expected until code exists. Refresh with `graphify update code` after modules land (AGENTS.md §10).

### [2026-10-24 14:55 UTC] ERROR Edited HackerRank's official AGENTS.md
- What happened: project rules had been appended to the official `AGENTS.md` as §10.
- Root cause: chose the auto-loaded file without considering ownership; official files may be updated upstream (merge conflicts) and must stay pristine.
- Fix: moved the rules to `AGENTS.md §10`; restored `AGENTS.md` via `git checkout`; auto-load via `CLAUDE.local.md` (`@AGENTS.md §10`), so official `CLAUDE.md` is untouched too. Added an explicit "never edit official files" rule. Updated all doc references from "AGENTS.md §10" to project_rules.md.
- Follow-up: graphify graph still has nodes sourced from the old AGENTS.md §10 — refresh on next doc rebuild.

### [2026-10-24 15:05 UTC] DECISION Rules back in AGENTS.md §10; docs at repo root (supersedes the two entries above)
- User decision: keep the project rules in `AGENTS.md` as §10 (auto-loaded via the official `CLAUDE.md` → `@AGENTS.md`), and keep `design_doc.md`, `roadmap.md`, `system.md` at the repo root beside `AGENTS.md` and `question.md`.
- Done: rebuilt §10 (additions only; §0–§9 untouched), moved the three docs out of `code/docs/` (folder removed), deleted `code/docs/project_rules.md` and `CLAUDE.local.md`, fixed all links. Rule now reads "§0–§9 are read-only; only §10 is ours".
- Consequence: the docs are no longer inside `code/`, so the `code.zip` command must add them explicitly (AGENTS.md §10.9). Graph refresh still pending.

### [2026-10-24 15:30 UTC] DISCOVERY Full evidence-format inventory (roadmap M0 "deep data exploration")
- **SQL (24 files):** inventories use flat tables + `snapshot_scope(origin_system, captured_at)` listing which systems the snapshot covers (account 11, analytics/integration/search/security/support 10, backup 9, export 8) → absence is only provable for in-scope systems. Replica captures store `record_json` in `customer_data_{primary,read_replica,replica_ap_south,replica_eu_west,reporting_replica,failover_replica}` (+ `origin_system`, `collection_name`); failover accounts use `customer_profiles_{primary,failover_replica}`; `search_documents_primary` has `source_resource_id` (search→account link). Header comment `-- Captured at:` gives time. Decoy near-names present (Jonas Berg vs Jonas Berglund / Joana Berg).
- **JSON:** (a) snapshot bundles `snapshots[].{captured_at,data_store,collection,records}` — empty `records` = coverage with zero rows (absence proof, sample case_31 cites it); collections include `identity_service.deleted_customer_references` (tombstones) and `security_audit_events`. (b) record-style exports (`connector_configurations`, `customer_export_manifest`, `security_audit_ledger`) with explicit `record_type` + `result` ∈ {FOUND, NOT_FOUND, IDENTIFIABLE, ANONYMIZED, REDACTED, ACTIVE, DISABLED, BLOCKED}; includes `legal_service LEGAL_HOLD_RECORD`. (c) `service_resource_export_*`: `service_exports[system][collection][]` with `observed_at`; account `status_code 404` = absent; search `hits.total 0` = absent. (d) analytics report & export jobs: flat `captured_at` + records.
- **Logs (≥7 dialects):** kv `service= event=`; bracketed `[svc] [trace] event:`; pipe-delimited; JSON-per-line; syslog `<pri>1 host app trace`; cloud-runtime escaped `message="..."` (function=profile_service); `record_lookup` lines with explicit system/record_type/result/subject_reference. Identifier is on the `*_started` line (`lookup_key`/`match_key`/`subject_key`), state on `*_completed` (`rows=0`/`http_status=404` = absent) — must join by trace id.
- **TXT handover:** pipe rows `ts | system | resource | RECORD_TYPE | RESULT | identifier`.
- **PDFs (pypdf works, no VLM needed):** support attachment `support_001` with full PII (case_07); legal-hold register rows `ORD | user_NN | … | Retain until`; compliance extract `audit_record_003 / user_03 / retain until`; account statement `NST-2026-0718-1842 / user_18`.
- **Activity details:** `CHECK_DATA_FLOW` "remains enabled" and `CHECK_RESTORE_ACCESS` "can still be restored" are citable risk proofs; `SYNC_RECORD … Active connector repopulated` and `RESTORE_BACKUP … repopulated` = resurrection; `LINK_RESOURCE_IDENTITY` gives explicit resource↔email↔user links (one says attachment "belongs only to" a subject → SUPPORT_ATTACHMENT); `CLASSIFY_REQUEST` "non-deletion" = NOT_APPLICABLE signal; DELETE_RECORD results 302 SUCCESS/368 FAILED/220 PARTIAL (claims only).

### [2026-10-24 16:20 UTC] RESULT Batch 1 — ingestion layer complete (M1 except images)
- Built `code/exorcist/{config,ids,model,store}.py` and `loaders/{sql,json_,logs,text,pdf,activity}.py`; CLI `python code/main.py --coverage`.
- Numbers: 6,913 observations, 4,841 resources, 1,284 identifier keys, 359 scopes; full compile **0.24 s**. 82/83 non-image evidence files yield observations; `evidence_90` is scope-only (account_service captured with zero rows = absence proof). 11 PNGs await the VLM step (M5).
- Acceptance: **75/75 evidence citations in sample_output.csv are reproduced** by the store (direct observation, or absence proven by a scope). `pytest code/tests`: **16 passed**.
- Dependencies pinned in `code/requirements.txt`: pypdf 6.12.2, pytest 8.3.3.

### [2026-10-24 16:20 UTC] DISCOVERY Catalog aliases + two more systems
- `LINK_RESOURCE_IDENTITY` details carry an alias in parentheses: `export_1842 (NST-2026-0718-1842)`, `object_19 (delivery_confirmation_19.pdf)`, `tombstone_17 (user_17)`. The statement PDF names only the alias, so the store resolves document references → resources through this map.
- New systems beyond the samples: `object_storage` (`object_`, attachment "belongs only to" one subject → SUPPORT_ATTACHMENT) and `marketing_platform` (`marketing_`, MARKETING_PROFILE). Added to the data-driven prefix map.

### [2026-10-24 16:20 UTC] ERROR Regex `\b` silently became a backspace character
- What happened: `DOC_REF_RE` matched nothing; the statement PDF stayed at 0 observations.
- Root cause: editing code through the Bash tool converted the two-character sequence backslash-b into a literal 0x08 (backspace) inside the regex. Invisible in `grep`, visible in `od -c`.
- Fix: rebuilt the line with `chr(92)` and verified "backspaces left: 0". Rule going forward: edit Python source with the Edit/Write tools, never via shell string replacement; when a regex fails silently, byte-inspect with `od -c`.

### [2026-10-24 16:20 UTC] DECISION Absence proof = scoped capture without the row
- A capture proves a resource absent only for systems it enumerates: inventory tables only for systems in `snapshot_scope`; replica/primary tables for the systems they hold; bundle collections (even empty ones); readbacks with `rows=0`/`404`/`NOT_FOUND`/zero hits. Matches every ABSENT citation in the samples (e.g. evidence_54 for account_001, evidence_51 empty profiles collection).

### [2026-10-24 17:40 UTC] RESULT Batch 2 — identity, discovery, state, policy
- Built `identity.py` (time-bounded guarded union-find, sha256 hash keys, phone normalization), `matcher.py` (Aho-Corasick, pure-Python + optional C ext), `discovery.py`, `state.py`, `policy.py`. 27 tests pass.
- All 550 request emails (32 sample + 518 test) resolve to a user; discovery for all 550 in 0.32 s.
- **Per-resource decision accuracy on gold resources: 111/111; citation accuracy 75/75** (finding/verification op + evidence_id). Discovery on samples: TP 100 / FP 33 / FN 11.
- Resurrection detector flags 8 resources corpus-wide.

### [2026-10-24 17:40 UTC] DECISION Answers to design_doc §14 Q1–Q4
- **Q1/Q2 (treatment):** the treatment the deletion workflow *attempted* (DELETE/REDACT/ANONYMIZE_RECORD, DISABLE/CHECK_DATA_FLOW, BLOCK/CHECK_RESTORE) is the organization's classification of that resource; its reported result is only a claim. Priority: workflow action > explicit evidence record_type (e.g. handover SUPPORT_ATTACHMENT, attachment PDFs) > system default → deletion_rules.csv. Explains analytics_9914 → DELETE and support DELETE vs REDACT.
- **Q3 (discovery):** identifiers first (incl. trace-joined lookup keys, nested `document` PII, `subject_ref`). Resources whose identifiers are already gone (deleted accounts, anonymized analytics) are linked only by the deletion workflow's own actions within ±2 h of `reported_at`; contested resources go to the closest request; one primary account per subject (identifier-linked wins).
- **Q4 (citation):** cite the latest *visible* direct observation that decides the state. Visible = observation time ≤ audit_at **and evidence file captured_at ≤ audit_at**. Absence proofs: global SQL captures with ≥1 row, or subject-scoped bundles that are about this subject; empty global captures are ignored. Process status (ACTIVE/DISABLED/BLOCKED) only from observations stating it.

### [2026-10-24 17:40 UTC] ERROR Three state bugs found by the per-resource validator
- (1) Bundle snapshot `evidence_02` (captured 09-17) contains internal timestamps of 09-15 and leaked into 09-15 audits → fixed with a file-level captured_at cutoff. (2) Snapshot bundles were treated as global absence proofs, falsely "deleting" retained audit records → bundles are now subject-scoped scopes. (3) Backup restore risk was hidden by later plain "found" lines → process status uses only status-bearing observations. Result went 103/111 → 111/111.

### [2026-10-24 17:40 UTC] DISCOVERY Unobservable gold resources (hard ceiling)
- `account_004` (case_04), `audit_record_6645` (case_18), `audit_record_5569` (case_20) appear in no participant evidence (text or images checked). ~3/111 gold resources cannot be derived by any solver. Accounts of requests sharing an identical `reported_at` (cases 24–26) can only be separated by timing; residual mis-assignment is a known limit.

### [2026-10-24 17:40 UTC] DISCOVERY Screenshots carry identity links
- e.g. account admin console: `user_11 · account_5762 · haruka.s1838@zoho.com · +81 90 7610 2507 · support_9538`; reference registry: `user_17` retained reference. Needed for some test cases → M5 VLM extraction matters for scoring.

### [2026-10-24 18:30 UTC] RESULT Batch 3 — first full output.csv
- Built `intent.py` (multilingual lexicon tier), `planner.py` (decision table, canonical sort, serializer), `auditor.py` (end-to-end), CLI `main.py` (`--input/--output/--explain/--coverage`), `evaluation/main.py` (all contract metrics + invariant checker + auto-written report block). 32 tests pass.
- **Samples: status 100% (32/32), step F1 90.7% (P 90.3 / R 91.2), evidence accuracy 99.4%, sequence/exact 46.9%, Levenshtein sim 86.8%.**
- **Full run: 518 rows in 0.64 s total** (347 INCOMPLETE / 161 COMPLETE / 10 NOT_APPLICABLE), **0 invariant violations**, two runs byte-identical.
- Independent cross-check: the 10 NOT_APPLICABLE subjects are exactly the 10 accounts the privacy-intake system logged as "classified non-deletion" (CLASSIFY_REQUEST) — 10/10, though the gate never reads those events.

### [2026-10-24 18:30 UTC] ERROR Intent gate rejected follow-up deletion requests
- First run marked 5 deletion cases NOT_APPLICABLE ("remove that search result", "confirm the profile is gone", "switch off any integration"). Root cause: requiring a classic deletion verb. Fix: override intents decide NOT_APPLICABLE; absent an override the request (which arrived via the deletion channel) is a deletion; LLM tier reserved for undecided texts. Status accuracy 84.4% → 100%.

### [2026-10-24 18:30 UTC] DECISION Retained records documented only after audit_at
- Gold INCOMPLETE cases verify audit records (e.g. audit_record_4128) that appear only in a bundle filed after audit_at. Verification steps of INCOMPLETE cases are *future* checks with no citation, so discovery may use later evidence for RETAIN resources only; state, findings and citations still use visible evidence only. COMPLETE verdicts keep only evidence-backed steps (fixed the single invariant violation, case_532).

### [2026-10-24 18:30 UTC] DECISION One-to-one assignment of workflow-only resources; natural case order
- Workflow-only resources are assigned greedily one-to-one (resource→one request, request→≤1 per system, never into a system already identifier-linked), preferring resources with visible direct evidence, then the smallest timing gap. Residual errors are swaps between requests with identical `reported_at` (cases 24–26, 27–29, 31–32) — verified that activity order, requested_at and gaps carry no signal; accepted as a data-level ceiling.
- Output sorted in natural case order (case_33 … case_550), matching the request file; string order would put case_100 first.

### [2026-10-24 19:40 UTC] RESULT Batch 4 — LLM/VLM edges, custom cases, ablations, reports
- Provider: Groq (key in gitignored `.env`). `openai/gpt-oss-20b` = intent fallback; `qwen/qwen3.8-27b` = vision (1.0 s per screenshot). All responses cached by content hash in `code/cache/llm/`; reruns make 0 calls and are byte-identical.
- Screenshots: 11/11 extracted (28 validated observations). Changed ~10 test rows in the intended direction (case_34 account still live on the 09-26 admin console; case_39 connector `data_flow_1121` continuous; case_50 analytics profile still identifiable).
- Intent audit: rules vs LLM on all 398 unique texts → 393/398 agree; the 5 disagreements were LLM errors on deletion follow-ups (samples case_25/26 prove the rules right). Prompt fixed → LLM 11/11 on the 5 hard texts + 6 novel multilingual probes. Production: rules decide 393, the LLM decides the 5 texts the lexicon cannot place.
- **Samples: status 100%, step F1 92.0%, evidence 99.4%, sequence 50.0%. Custom cases 8/8.** Baseline "trust reported_status" = 53.1% status accuracy.
- Ablations (status / F1 / custom passed / test rows changed): no_history 90.6% / 83.8% / 7 / 147 · trust_claims 90.6% / 88.9% / 3 / 143 · no_workflow_link 96.9% / 91.3% / 5 / 317 · no_scoped_absence 100% / 92.4% / 6 / 73 · no_replicas 100% / 91.2% / 7 / 69 · no_vlm 100% / 92.0% / 8 / 9 · rules_only_intent 100% / 92.0% / 7 / 0.
- Usage (final run): 16 model responses (5 intent + 11 vision), 25,799 in / 7,269 out tokens, ≈ $0.0112 total, ≈ $0.000022 per request. Development total 41 network calls, 66.9k tokens, ≈ $0.017 (free tier, $0 billed).

### [2026-10-24 19:40 UTC] ERROR Same person's two requests competed for their own resources
- Found by custom cases C1/C3/C6 (5/8 → 8/8): one-to-one workflow assignment treated each request as a claimant, so a duplicate/follow-up request from the same subject lost that subject's account to the other request. Fix: claimants are people (uid), not requests. Also improved samples (F1 90.7 → 92.0%) because two subjects appear in both the sample and test sets.

### [2026-10-24 19:40 UTC] ERROR Ablation that measured nothing; Groq rate limits; module shadowing; shell quoting
- `trust_claims` ablation first showed 0 effect: it only added claims as early events, which the lattice correctly overrode. Re-implemented as a true dashboard baseline (SUCCESS claim overrides evidence) → 90.6% status, 5 custom failures.
- Groq free tier: 7k input tokens/min on the vision model → HTTP 429. `llm.py` now honours the "try again in Ns" hint (up to 8 retries).
- `evaluation/main.py` put its own folder first on `sys.path`, shadowing `code/main.py`; fixed by appending instead.
- A long multi-heredoc shell command failed to parse (quotes inside heredocs); bookkeeping edits now go through script files.

### [2026-10-24 19:40 UTC] DECISION Object storage and legal registers are evidence-only
- After screenshots, `case_07` gained an `object_19` (blob in object storage) finding not in gold — the regression gate caught it. Attachment blobs are remediated through their owning support record; order registers (ORD-…) are not resources. Both kept for identity linking, excluded from steps.

### [2026-10-24 20:30 UTC] DECISION 30-day freshness window for state
- Every citation in the labelled samples is ≤ 5 days older than audit_at; scenarios are judged on recent captures. A 7-month-old screenshot showing `object_19` explained the false finding in case_07 and the *true* one in case_61 (1 day old). Replaced the blanket "object storage is evidence-only" rule with: direct observations and scoped absence proofs older than audit_at − 30 d do not decide state (activity history still informs treatment). Samples unchanged (100% / 92.0%); custom 8/8.

### [2026-10-24 20:30 UTC] ERROR Three deletion cases had empty plans; one legal-register row leaked (output scan)
- case_46: screenshot id `user_17` dropped by the image loader (not a resource pattern) → now unbound ids survive only if a catalog alias maps them (user_17 → tombstone_17); tombstones are verified when they exist; an account proven absent is used when the subject has no other account. case_55: archive listed in a recovery console without a block marker is restorable → restore risk. case_61: freshness rule (above). The legal_service row came through the "documented after audit_at" path, which skipped the evidence-only filter — the filter now applies before any planning. 8/518 rows changed.

### [2026-10-24 20:30 UTC] RESULT Submission artifacts ready
- `output.csv`: 518 rows (356 INCOMPLETE / 152 COMPLETE / 10 NOT_APPLICABLE), natural case order, 0 invariant violations, byte-identical reruns, 0.57 s.
- `code.zip`: 78 files / 115 KB = `code/` + design_doc.md, roadmap.md, system.md; excludes dataset, .env, question.md, prediction caches; secret scan clean. **Clean extract + dataset copy + no API key → byte-identical output.csv** and 32/32 tests (offline from the committed LLM cache).
- Reports regenerated from the final run: evaluation_report.md (100% status, 92.0% F1, 99.4% evidence, 50.0% sequence, 8/8 custom, ablations) and usage_report.md (16 responses, 33,068 tokens, ≈ $0.011).
- graphify refreshed with code: 446 nodes, 927 edges, 15 communities. log.txt: 12 valid entries.

### [2026-10-25 02:30 UTC] RESULT Batch 6 — stronger math, lower latency
- Latency (warm, in-process): compile ≈0.1 s, audit 0.165 s = **0.32 ms/request**; end-to-end ≈0.3 s (was 0.57 s). Compile-once pickle cache keyed by SHA-256 of (dataset file path/size/mtime via one scandir pass ‖ loader source ‖ ablations); lazy pypdf; bisect over time-sorted scopes (removed ~88k redundant checks). Usage accounting preserved through the cache.
- Assignment: Hungarian (Kuhn–Munkres) min-cost matching per system and connected component, cost = −log N(offset; μ_sys, σ_sys) + 50·[never directly observed]. Timing model = per-system Gaussian with empirical-Bayes shrinkage (K=3), fit offline on public samples (`fit_timing.py` → `timing_model.json`).
- **Samples: status 100%, step F1 93.3% (P 92.4 / R 94.3), sequence 56.2%, evidence 99.5%; 4-fold CV identical** (no overfit). Ablations: greedy 92.0% / 50.0% seq; pooled timing 92.5% / 53.1%. 121 test rows changed vs greedy.
- Confidence: naive-Bayes log-odds fusion (source reliabilities, 7-day half-life) × softmax assignment posterior → AUROC 0.946, Brier 0.071 on sample resources. Decision-neutral.
- 39 tests pass; 0 invariant violations; deterministic.

### [2026-10-25 02:30 UTC] ERROR Hungarian augment step bug
- First integration dropped recall to 84.5% and changed exactly as many rows (317) as the no-workflow ablation — the matcher assigned nothing. Root cause: augmenting-path update wrote `p[j0] = j1` instead of `p[j0] = p[j1]`. Caught by an isolated test; fixed; now verified against brute-force enumeration on 300 random matrices (0 mismatches) and kept as a unit test.

### [2026-10-25 02:30 UTC] DECISION Submission is treated as single-shot
- The challenge page states the AI-judge interview opens after a successful submission and stays open 12 h; no resubmission rule is documented. Plan: finish, re-verify, submit once with buffer before close (~25 Oct 19:00 IST), interview window ends 26 Oct 06:00 IST.
