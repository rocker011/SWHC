# HyperGraphRAG Evaluation Run Guide

## Environment
- Activate env: `conda activate hypergraphrag`
- Working directory: `D:\PythonProjects\HyperGraphRAG\evaluation`
- API config file: `D:\PythonProjects\HyperGraphRAG\api_config.txt`
- Current stable mode: remote LLM + local embedding (`local:Qwen/Qwen3-Embedding-0.6B`)

## Recommended Safe Concurrency
- Step1 build graph:
  - `HGRAG_INSERT_LLM_MAX_ASYNC=8`
  - `HGRAG_ENTITY_SUMMARY_LLM_MAX_ASYNC=1`
- Step1 official GraphRAG indexing:
  - default local embedding path assumes Ollama OpenAI-compatible API at `http://127.0.0.1:11434/v1`
  - override with `HGRAG_GRAPHRAG_EMBED_API_BASE` if your endpoint is elsewhere
- Step2 retrieve knowledge:
  - `HGRAG_QUERY_CONCURRENCY=2`
- Step2 official GraphRAG local context:
  - `HGRAG_GRAPHRAG_COMMUNITY_LEVEL=2`
- Step3 generation:
  - `HGRAG_GENERATION_WORKERS=2`
- Step4 scoring:
  - `HGRAG_SCORE_WORKERS=2`
  - `HGRAG_GEN_METRIC_WORKERS=1`
  - `HGRAG_ENABLE_LLM_JUDGE=false` if you want to skip `Gen` during intermediate experiments

## Step1 Build Graph
```powershell
conda activate hypergraphrag
cd /d D:\PythonProjects\HyperGraphRAG\evaluation
set PYTHONIOENCODING=utf-8
set HGRAG_INSERT_LLM_MAX_ASYNC=8
set HGRAG_ENTITY_SUMMARY_LLM_MAX_ASYNC=1
python script_insert.py --cls hypertension
```
Expected outputs in `expr/hypertension`:
- `graph_chunk_entity_relation.graphml`
- `kv_store_full_docs.json`
- `kv_store_text_chunks.json`
- `vdb_chunks.json`
- `vdb_entities.json`
- `vdb_hyperedges.json`

## Step2 Retrieve Knowledge
```powershell
set HGRAG_QUERY_CONCURRENCY=2
python script_hypergraphrag.py --data_source hypertension
```
Expected output:
- `results/HyperGraphRAG/hypertension/test_knowledge.json`

## Official GraphRAG Step1 Index
`GraphRAG` in the evaluation chain now means **Microsoft official GraphRAG**.

Because the current project default embedding is local `Qwen/Qwen3-Embedding-0.6B`, official GraphRAG needs an **OpenAI-compatible embedding endpoint** for Step1/Step2. In the current project setup this means Ollama's OpenAI-compatible API. Before running, set:

```powershell
set HGRAG_GRAPHRAG_EMBED_API_BASE=http://127.0.0.1:11434/v1
set HGRAG_GRAPHRAG_EMBED_MODEL=qwen3-embedding:0.6b
set HGRAG_GRAPHRAG_EMBED_API_KEY=ollama
```

Behavior note:
- official GraphRAG now applies a local DeepSeek JSON-mode compatibility patch for `community_reports`
- embedding `vector_size` is auto-detected from the embedding endpoint before writing `settings.yaml`
- if you need to override it manually, set `HGRAG_GRAPHRAG_EMBED_VECTOR_SIZE`

Index command:

```powershell
python script_graphrag_index.py --data_source hypertension
```

Optional smoke test:

```powershell
python script_graphrag_index.py --data_source hypertension --doc_limit 50 --workspace_suffix smoke --force_rebuild
```

Expected outputs under `expr_official_graphrag/hypertension/`:
- `input/documents.json`
- `output/entities.parquet`
- `output/relationships.parquet`
- `output/community_reports.parquet`
- `output/text_units.parquet`
- `output/lancedb/`

## Official GraphRAG Step2 Retrieve Knowledge
After official GraphRAG Step1 is complete:

```powershell
set HGRAG_GRAPHRAG_COMMUNITY_LEVEL=2
python script_graphrag.py --data_source hypertension
```

Expected output:
- `results/GraphRAG/hypertension/test_knowledge.json`

Behavior note:
- Step2 now extracts only official `Entities / Relationships / Sources` context for fairness
- Step2 clears stale `GraphRAG` generation / score files because the old internal `GraphRAG` outputs are no longer valid after the implementation switch
- if you keep the project default local embedding name `local:Qwen/Qwen3-Embedding-0.6B`, the adapter automatically maps it to Ollama's `qwen3-embedding:0.6b`

## Step3 Generate Answers
```powershell
set HGRAG_GENERATION_WORKERS=2
python get_generation.py --data_sources hypertension --methods HyperGraphRAG
```
Expected output:
- `results/HyperGraphRAG/hypertension/test_generation.json`
- each sample records `generation_usage` and flattened consumed-token fields when the backend returns usage

## Step4 Score
```powershell
set HGRAG_SCORE_WORKERS=2
set HGRAG_GEN_METRIC_WORKERS=1
python get_score.py --data_source hypertension --method HyperGraphRAG
```

Skip LLM judge and only compute `EM / F1 / R-Sim`:
```powershell
set HGRAG_SCORE_WORKERS=2
set HGRAG_ENABLE_LLM_JUDGE=false
python get_score.py --data_source hypertension --method HyperGraphRAG --enable_llm_judge false
```

Expected outputs:
- `results/HyperGraphRAG/hypertension/test_result.json`
- `results/HyperGraphRAG/hypertension/test_score.json`
- `test_score.json` includes `avg_consumed_tokens` when Step3 usage is available

## Step5 Split Report
```powershell
python see_score.py --data_source hypertension --method HyperGraphRAG
```
Expected console output:
- binary / n-ary / overall score table

## Common Failure Modes
- `429 Too Many Requests`:
  - lower `HGRAG_QUERY_CONCURRENCY`, `HGRAG_GENERATION_WORKERS`, or `HGRAG_SCORE_WORKERS`
  - keep `HGRAG_ENTITY_SUMMARY_LLM_MAX_ASYNC=1`
- Official GraphRAG LanceDB write fails with `ArrowInvalid: The length of the values Array needs to be a multiple of the list_size`:
  - this usually means the configured `vector_size` does not match the actual embedding dimension
  - the current adapter auto-detects this for the default Ollama path
  - if you use a different embedding endpoint, set `HGRAG_GRAPHRAG_EMBED_VECTOR_SIZE` explicitly and rerun Step1
- Empty graph or empty vdb files:
  - check `api_config.txt`
  - inspect `hypergraphrag.log`
- Slow first run of Step4:
  - `sup-simcse-roberta-large` downloads on first use
- Windows encoding issues:
  - keep `PYTHONIOENCODING=utf-8`

## What To Check After Each Step
- Step1: graph and vdb files are non-empty
- Official GraphRAG Step1: `expr_official_graphrag/<dataset>/output/` contains non-empty parquet outputs
- Step2: `test_knowledge.json` has 512 rows and every row has non-empty `knowledge`
- Official GraphRAG Step2: `results/GraphRAG/<dataset>/test_knowledge.json` is regenerated from the official baseline and no stale Step3/Step4 files remain
- Step3: `test_generation.json` has 512 rows and no `[ERROR]` generation
- Step4: `test_score.json` exists and prints overall metrics
