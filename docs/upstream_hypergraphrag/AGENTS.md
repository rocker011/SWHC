# AGENTS.md

## Scope
This repository is for implementing and evaluating **SWHC (Semantic Wiener HyperConnector)** on top of **HyperGraphRAG**.

Use this file for **persistent project rules**.
Use `TASK.md` for the current phase and priorities.
Use `EXPERIMENT_LOG.md` for append-only experiment records.

## Project stage note
The baseline implementation phase is complete for the current main stack.

That means:
- default to the active **Research TODO** items in `TASK.md`
- do not reopen completed baseline plumbing unless it is necessary for a specific research question
- treat the current fair six-method `hypertension` no-judge table as the default reference snapshot

## Start-of-session rules
At the start of each new work session:

1. Read `AGENTS.md`
2. Read `TASK.md`
3. If the work is experiment-related, also read `EXPERIMENT_LOG.md`
4. Then continue implementation, evaluation, or documentation

Do not restart planning from scratch if these files already answer the question.

## Project purpose
The project has two layers:

1. **Method research**
   - `SWHC` is a query-time evidence assembly method
   - It preserves HyperGraphRAG’s indexing/build stage
   - It replaces the query-time context assembly stage

2. **Paper-oriented reproduction**
   - Baselines, datasets, metrics, docs, and result tables should support a CCF-A/B style submission
   - Comparisons must stay fair and reproducible

## Fixed method scope
Base method:
- `HyperGraphRAG`

Proposed method:
- `SWHC`

High-level claim:
> HyperGraphRAG solves n-ary fact representation; SWHC improves query-time evidence assembly by selecting a compact, semantic-weighted connector subgraph.

## SWHC method essentials
### What SWHC changes
SWHC does **not** change the build/index stage. It keeps:

- document loading
- chunking
- entity / hyperedge extraction
- bipartite hypergraph construction
- chunk / entity / hyperedge indexing

SWHC only changes the **query-time context assembly** stage:

- HyperGraphRAG:
  - retrieve local/global evidence
  - expand one-hop neighborhoods
  - merge text context heuristically
- SWHC:
  - retrieve entity/hyperedge seeds
  - build a query-specific candidate subgraph
  - select a semantic-weighted connector subgraph
  - export `Entities / Relationships / Sources`

### What the LLM finally receives
Even for graph-based methods, the final LLM input is **not** a graph object or vector. It is a text-formatted context with:

1. `Entities`
2. `Relationships`
3. `Sources`

So SWHC changes retrieval assembly, while keeping the downstream interface compatible with the existing generation pipeline.

### Core algorithm idea
Current SWHC is a **practical heuristic solver**, not an exact MWC solver and not the original Wiener Connector approximation algorithm.

The current search pattern is:

1. retrieve entity and hyperedge seeds
2. choose high-priority terminals
3. build a local candidate subgraph
4. initialize a connector using shortest-path / MST-style construction
5. greedily add bridge paths if they reduce the objective
6. prune low-value leaf nodes if pruning reduces the objective

The intended effect is:

- keep important terminals close
- prefer semantically stronger paths
- avoid bloated context

### Core objective
For query $q$, let:

- $T_q$ be the selected terminal set
- $H$ be the final evidence subgraph
- $\pi_q(t)$ be the normalized terminal importance weight
- $d_H^{\text{sem}}(u,v)$ be the semantic shortest-path distance inside $H$

The terminal-aware Wiener term is:

$$
W_{\text{SWHC}}(H \mid q)
=
\sum_{u,v \in T_q,\; u < v}
\pi_q(u)\,\pi_q(v)\,d_H^{\text{sem}}(u,v)
$$

Semantic edge cost is:

$$
w_{\text{sem}}(i,j)
=
\max\left(
\varepsilon,\;
\frac{1}{\sqrt{\max(conf(i,j),1)}}
+
\left(1 - \frac{s(i)+s(j)}{2}\right)
+
c_{\text{hop}}
\right)
$$

The full practical objective is:

$$
J(H \mid q)
=
\alpha \, W_{\text{SWHC}}(H \mid q)
+
\beta \sum_{v \in V(H)}
\left(
\frac{\text{Tok}(v)}{256}
+
1 - s(v)
\right)
+
\gamma |V(H)|
$$

Interpretation:

- first term:
  - keep important terminals close
- second term:
  - penalize long or weakly relevant nodes
- third term:
  - penalize subgraph size

Current default parameters:

- $\alpha = 1.0$
- $\beta = 0.15$
- $\gamma = 0.05$
- $\varepsilon = 0.05$
- $c_{\text{hop}} = 0.25$
- source rerank at context export:
  - implemented but disabled by default for the current research path
  - project convention from `2026-05-06`: keep it off for normal SWHC runs; only enable it for an explicit rerank ablation with `HGRAG_SWHC_SOURCE_RERANK=true`
  - applies only to `Sources` ordering after the SWHC subgraph is selected
  - score combines structural support, query/source lexical overlap, terminal coverage, node-score support, and a length penalty
  - this is a query-time assembly change; SWHC results before and after enabling it are not directly comparable without qualification

### Method invariants
When modifying SWHC, preserve these unless explicitly changing the method:

1. final output remains `Entities / Relationships / Sources`
2. SWHC remains a query-time assembly method, not a new indexing method
3. evaluation-side implementation under `evaluation/hypergraphrag/` is the authoritative one
4. if the objective or solver changes, report that previous SWHC results may no longer be directly comparable

## Fixed baseline set
The target baseline set is:

1. `NaiveGeneration`
2. `BM25`
3. `StandardRAG`
4. `Hybrid RAG (BM25 + Dense)`
5. `GraphRAG (official)`
6. `LightRAG`
7. `PathRAG`
8. `HyperGraphRAG`
9. `SWHC`

Do not silently add or remove baselines without updating task and planning documents.

Baseline implementation is no longer the default active phase.
If new baseline work is proposed, justify it with a concrete research need.

## Fixed dataset set
The target dataset set is:

1. HyperGraphRAG five-domain benchmark
   - `hypertension`
   - `agriculture`
   - `cs`
   - `legal`
   - `mix`
2. `HotpotQA`
3. `2WikiMultiHopQA`
4. `MuSiQue`
5. `PopQA`

Interpretation:
- the five-domain benchmark is the **mechanism-analysis axis**
- the public datasets are the **generalization axis**

## Runtime defaults
### Environment
- Conda env: `hypergraphrag`

### API / model defaults
- API / model defaults are read from `api_config.txt`
- Current verified API base: `https://ai.butel.com/api`
- Current verified main chat model: `gpt-5.4-mini-hy`
- Judge model:
  - by default follows the same configured chat model
  - if a separate judge model is needed, override it with `HGRAG_JUDGE_MODEL`
- Embedding: local `Qwen/Qwen3-Embedding-0.6B`

Do not reintroduce the old Qiniu-specific batch path unless explicitly requested.

### Intermediate experiment default
For intermediate runs, disable LLM judge by default.

That means:
- compute `EM / F1 / R-Sim` first
- defer `Gen` until final experiments or milestone runs

Supported switches:
- CLI: `--enable_llm_judge false`
- Env: `HGRAG_ENABLE_LLM_JUDGE=false`

## Codebase structure rules
### Authoritative implementation for evaluation
For paper-style evaluation, the authoritative implementation is under:

- `evaluation/hypergraphrag/...`

The root package under:

- `hypergraphrag/...`

should stay reasonably aligned, but evaluation-side behavior is the reproduction reference.

### Method entrypoints
Method scripts should live under:

- `evaluation/methods/`

Thin wrapper scripts may remain under:

- `evaluation/script_*.py`

### Results layout
Use:

- `evaluation/results/<Method>/<dataset>/...`

Expected files per method/dataset:
- `test_knowledge.json`
- `test_generation.json`
- `test_result.json`
- `test_score.json`

### Docs layout
Project docs:
- `docs/project/...`

Result analysis docs:
- `docs/results/...`

Figures:
- `docs/figures/...`

## Development rules
### Preserve working paths
Do not make broad refactors that risk breaking:
- `HyperGraphRAG`
- `SWHC`
- evaluation scripts

Prefer minimal changes.

### Avoid unnecessary reruns
Do not rerun already finished pipelines unless explicitly requested.

In particular:
- do not rerun finished multi-step dataset pipelines just to “check”
- reuse existing indexes and outputs when possible
- prefer targeted research ablations over reopening completed baseline runs

### Git policy
Git should track:
- code
- docs
- scripts
- summaries

Git should not track:
- API keys
- raw datasets
- indexing artifacts
- experiment result JSONs
- large logs

### Documentation update policy
After any meaningful milestone, update at least one of:
- `TASK.md`
- `EXPERIMENT_LOG.md`
- docs under `docs/project/`

Do not leave important decisions only in chat history.

## Research quality rules
- Preserve already verified pipelines whenever possible
- Keep experiment progress incremental and reproducible
- Keep method comparisons fair
- Do not silently change preprocessing, evaluation definitions, dataset splits, or scoring behavior
- Do not silently change baseline scope or dataset scope
- If a change may invalidate previous results, say so explicitly before proceeding

## Evaluation rules
Current official metrics in use:
- `EM`
- `F1`
- `R-Sim`
- `Gen` (optional during intermediate runs)
- `Average Context Tokens`
- `Average Consumed Tokens` (when Step3 usage is available)

Desired additions later:
- `Supporting Fact Recall / F1`
- `F1 per Token`
- `Terminal / Source counts`

Experiment logs and score files should record `Average Consumed Tokens` whenever the generation backend returns token usage.

## Review guidelines
Treat the following as high-risk:
- preprocessing changes
- dataset split changes
- metric definition changes
- retrieval logic changes that break comparability
- silent changes to evaluation outputs

For experiment-affecting changes, always report:
1. files changed
2. exact command run
3. dataset
4. method
5. whether LLM judge was enabled
6. output path
7. what remains unverified

## Codex usage guidance
Good prompts for future sessions:
- “Read `AGENTS.md` and `TASK.md`, then continue the current priority.”
- “Read `AGENTS.md`, `TASK.md`, and `EXPERIMENT_LOG.md`, then update the experiment plan.”
- “Advance the next `Research TODO` item following `AGENTS.md` and update `TASK.md` when done.”

When project direction changes, update `AGENTS.md`.
When current focus changes, update `TASK.md`.
When an experiment runs or fails, append to `EXPERIMENT_LOG.md`.
