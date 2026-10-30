# EXORCIST — deletion auditor for *Ghost Data Still Exists*

EXORCIST decides, for every deletion request, whether the person's data is **really** gone at
`audit_at`. It cites the evidence that proves each conclusion, and it writes the ordered
FINDING → REMEDIATION → VERIFICATION plan needed to finish the job.

| Result | Value |
|---|---|
| Sample case-status accuracy | **100%** (32/32) |
| Sample step F1 / evidence accuracy | **93.3% / 99.5%** (4-fold cross-validated: identical) |
| Custom fault-injection cases | **8/8** |
| "Trust the dashboard" baseline (`reported_status`) | 53.1% |
| Full 518-request run | **≈0.3 s warm** (0.32 ms per request), 0 contract-invariant violations, byte-identical reruns |
| Per-step confidence quality | AUROC **0.946**, Brier 0.071 |
| Model usage for the full run | 16 cached responses, ≈33k tokens, ≈$0.011 |

Full reports: [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md) and
[`evaluation/usage_report.md`](evaluation/usage_report.md). The design (with prior art from the US
and China) and the build journal are in `design_doc.md`, `roadmap.md` and `system.md`, which ship
beside this folder in `code.zip`.

## Setup

Requires Python 3.11+.

```bash
pip install -r code/requirements.txt        # pypdf (PDF evidence), pytest (tests)
```

Optional: an LLM key. Without a key, the pipeline runs **offline from the committed response cache**
(`code/cache/llm/`) and gives identical output. To refresh the cache, or to run on new data, put a key
in a `.env` file at the repo root (it is gitignored and never packaged):

```
GROQ_API_KEY=...                  # default provider (OpenAI-compatible API)
# EXORCIST_LLM_PROVIDER=openai|xai  with OPENAI_API_KEY / XAI_API_KEY
# EXORCIST_TEXT_MODEL=openai/gpt-oss-20b   EXORCIST_VISION_MODEL=qwen/qwen3.8-27b
```

## Run

Run these commands from the repository root (the folder that contains `dataset/`):

```bash
python code/main.py                                   # dataset/deletion_requests.csv -> ./output.csv
python code/main.py --explain case_61                 # provenance trace for one case
python code/main.py --coverage                        # what every evidence file contributed
python code/main.py --input dataset/sample_deletion_requests.csv --output /tmp/samples.csv

python code/evaluation/main.py --write-report --ablations   # metrics, invariants, custom cases, ablations
python code/evaluation/usage.py                              # token / cost report for the full run
python -m pytest code/tests -q                               # 39 unit tests
python code/evaluation/fit_timing.py                         # refit timing model (public samples)
```

## How it works (one paragraph per stage)

1. **Compile once.** Loaders turn all 94 evidence files into `Observation` rows in about 0.3 s. Formats:
   - SQLite dumps, including primary vs replica tables;
   - JSON bundles and exports;
   - 7 log dialects, joined per trace;
   - TXT handover notes;
   - PDFs via `pypdf`;
   - screenshots, read by a vision model once and cached.

   Each capture also records which systems it enumerated, so a missing row can *prove* absence.
2. **Who is the subject?** A time-bounded union-find over current identities plus `user_audit_log`
   resolves the request email, which may be historical, to every email, phone and SHA-256 email hash
   the person had at `audit_at`. Two different users are never merged.
3. **Which records are theirs?** Identifier links come first (one Aho-Corasick and hash-postings pass
   over everything). Records whose identifiers are already gone are linked by the deletion workflow's
   own actions around `reported_at`. These are assigned by an **optimal Hungarian matching** between
   people and resources. The cost is the negative log-likelihood under a **per-system Gaussian timing
   model with empirical-Bayes shrinkage**, fitted offline on the public samples and validated with
   4-fold cross-validation.
4. **What is true at `audit_at`?** An evidence-strength lattice decides: direct observations
   (snapshots, readbacks, documents, screenshots, scoped absence proofs) beat activity claims, which
   are never treated as proof. The rules applied at this stage:
   - Every replica is judged separately (replica drift).
   - Evidence filed after `audit_at`, or older than the 30-day freshness window, is ignored.
   - A sync or restore after a delete is flagged as a resurrection.
5. **What does policy require?** `deletion_rules.csv` is loaded as data. A resource's treatment comes
   from the action the deletion workflow attempted on it, then from an explicit evidence category,
   then from the system default. Retained records (security audit within retention, legal hold,
   backups) are never deleted. Tombstones keep only `user_id`.
6. **Plan.** Each violation becomes one finding, one remediation and one verification. Compliant
   resources become verifications that cite their proof. Steps are sorted by phase, then the
   contract's operation rank, then system, then resource. That order already disables flows and
   blocks restores before records are touched.
7. **Intent gate.** A multilingual lexicon decides clear cases. Explicit overrides (access, export,
   correction, marketing opt-out, "not a deletion") give `NOT_APPLICABLE`. The LLM classifies only
   the texts the lexicon cannot place.

8. **Confidence.** Each step carries P(state) × P(link). P(state) comes from naive-Bayes log-odds
   fusion of source reliabilities with exponential age decay; P(link) is a softmax over competing
   claimants. Confidence is reported in `--explain` and never changes a decision.
9. **Latency.** A compile-once corpus cache is keyed by a SHA-256 fingerprint of the dataset and the
   loader source code. Capture lookups use bisect. `pypdf` is imported lazily.

AI is used **only** at those two edges: reading language and reading pixels. Every scored decision is
deterministic code with unit tests.

## Layout

```
code/
  main.py                 CLI
  exorcist/               config, ids, model, store, identity, matcher, discovery,
                          state, policy, planner, intent, llm, auditor, loaders/
  evaluation/             main.py (metrics, invariants, ablations), custom_cases.py, usage.py,
                          evaluation_report.md, usage_report.md
  tests/                  pytest suite
  cache/llm/              content-hash cache of every model response (makes reruns offline + free)
  requirements.txt
```
