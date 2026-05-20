# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NeurIPS 2025 paper reproduction: **HyperGraphRAG** (hypergraph-structured RAG) plus a proposed query-time method **SWHC** (Semantic Wiener HyperConnector). The project has two layers: method research (SWHC improves query-time evidence assembly on top of HyperGraphRAG's indexing) and paper-oriented evaluation (fair multi-method comparisons across datasets).

## Session Protocol

1. Read `AGENTS.md` (persistent project rules)
2. Read `TASK.md` (current phase and priorities)
3. If experiment-related, also read `EXPERIMENT_LOG.md`

## Environment

```bash
conda activate hypergraphrag
# Python 3.11, Windows 11, CUDA GPU available
```

API/model config is read from `api_config.txt` at the repo root (4-line format: key, base_url, chat_model, embed_model). Embedding uses local `Qwen/Qwen3-Embedding-0.6B` by default.

## Key Commands

### Build knowledge hypergraph (root-level quick start)

```bash
python script_construct.py
python script_query.py
```

### Evaluation pipeline (run from `evaluation/`)

```bash
cd evaluation

# Step1: Insert contexts into graph index
python script_insert.py

# Step2: Retrieve knowledge for each method (method-specific scripts)
python script_hypergraphrag.py
python script_swhc.py
python script_standardrag.py
python script_graphrag.py
python script_naivegeneration.py
python script_bm25.py
python script_hybrid_rag.py

# Step3: Generate answers
python get_generation.py --data_sources <dataset> --methods <Method>

# Step4: Score
python get_score.py --data_source <dataset> --method <Method> --enable_llm_judge false

# Step5: View scores
python see_score.py
```

### Environment variables

| Variable | Purpose |
|----------|---------|
| `HGRAG_ENABLE_LLM_JUDGE` | `false` for intermediate runs (default: `true`) |
| `HGRAG_GENERATION_WORKERS` | Parallel generation workers (e.g. `4`) |
| `HGRAG_OPENAI_TIMEOUT_SECONDS` | API timeout (default `180`) |
| `HGRAG_JUDGE_MODEL` | Override judge model separately from chat model |
| `HGRAG_GENERATION_MODEL` | Override generation model |
| `HGRAG_INFERENCE_BACKEND` | `realtime` (default) or `batch` |
| `HGRAG_SHORTEST_ANSWER_SPAN` | `true` for shortest-span answer prompting |
| `HGRAG_SWHC_SOURCE_RERANK` | `true` to enable SWHC source reranking (off by default) |
| `HGRAG_FORCE_REGENERATE` | `true` to regenerate all samples (otherwise skips existing) |

## Architecture

### Two copies of `hypergraphrag/` package

- **`hypergraphrag/`** (root): upstream baseline package, reusable core code
- **`evaluation/hypergraphrag/`**: evaluation-time fork with patches — this is the **authoritative implementation** for paper results

### Core pipeline (root package)

```
hypergraphrag/
├─ hypergraphrag.py   # HyperGraphRAG class: insert() and query() orchestration
├─ operate.py         # chunking, entity extraction, kg_query dispatch
├─ swhc.py            # SWHC solver: solve_swhc() + format_swhc_context()
├─ base.py            # QueryParam dataclass, storage ABCs
├─ llm.py             # LLM/embedding function wrappers
├─ openai_config.py   # api_config.txt parser, model resolution
├─ storage.py         # JsonKVStorage, NanoVectorDBStorage, NetworkXStorage
├─ prompt.py          # prompt templates
└─ kg/                # optional KG backends (Neo4j, Milvus, MongoDB, etc.)
```

### Query flow

`HyperGraphRAG.query()` → `operate.kg_query()` dispatches based on `QueryParam.subgraph_selector`:
- `"union"` → standard HyperGraphRAG one-hop neighborhood expansion
- `"swhc"` → `swhc.solve_swhc()` → semantic-weighted connector subgraph
- `"graphrag"` → `graphrag_local.build_graphrag_context()` (internal reference only)

All paths produce the same final format: `Entities / Relationships / Sources` text context.

### Evaluation layer

```
evaluation/
├─ methods/           # method implementations (each exposes a run function)
├─ inference_backend.py  # RealtimeInferenceBackend / BatchInferenceBackend
├─ get_generation.py     # Step3: context → LLM answer (resume-friendly)
├─ get_score.py          # Step4: EM, F1, R-Sim, optional Gen (LLM judge)
├─ see_score.py          # Step5: display score table
└─ results/<Method>/<dataset>/  # test_knowledge/generation/result/score.json
```

### SWHC algorithm summary

Query-time only (does not change indexing). Given a query:
1. Retrieve entity/hyperedge seeds via embedding similarity
2. Select high-priority terminals
3. Build local candidate subgraph (k-hop expansion)
4. Initialize connector via shortest-path/MST construction
5. Greedy bridge-path addition (minimize weighted Wiener objective)
6. Prune low-value leaf nodes

Key parameters in `QueryParam`: `swhc_alpha`, `swhc_beta`, `swhc_gamma`, `swhc_edge_weight_floor`, `swhc_hop_cost`, `swhc_budget_nodes`.

## Datasets

- Five-domain benchmark: `hypertension`, `agriculture`, `cs`, `legal`, `mix`
- Public: `HotpotQA`, `2WikiMultiHopQA`, `MuSiQue`, `PopQA`

Dataset files live in `evaluation/datasets/<name>/questions.json` (gitignored).

## Metrics

- `EM` (Exact Match), `F1`, `R-Sim` (semantic similarity via SimCSE)
- `Gen` (LLM judge) — disabled for intermediate runs
- `Average Context Tokens`, `Average Consumed Tokens`

## Critical Rules

- SWHC is query-time assembly only; never modify the build/index stage
- Evaluation-side code (`evaluation/hypergraphrag/`) is the reproduction reference
- Do not silently change preprocessing, scoring, dataset splits, or evaluation definitions
- If a change invalidates prior SWHC results, state so explicitly before proceeding
- Source rerank is disabled by default; only enable for explicit ablation
- Do not rerun finished pipelines unless explicitly requested
- Keep method comparisons fair across all baselines
- LLM judge off for intermediate work (`HGRAG_ENABLE_LLM_JUDGE=false`)

## Results Layout

```
evaluation/results/<Method>/<dataset>/
├─ test_knowledge.json    # retrieved context per question
├─ test_generation.json   # LLM answers + token usage
├─ test_result.json       # parsed results
└─ test_score.json        # metric scores
```

## Git Policy

Track: code, docs, scripts, summaries.
Do not track: API keys, raw datasets, indexing artifacts (`expr/`), result JSONs, large logs.
