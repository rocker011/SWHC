# Method Runners

This folder contains the actual implementation entrypoints for retrieval-time baselines.

## Why this folder exists

The repository originally kept all `script_*.py` files directly under `evaluation/`.
That works for a small number of methods, but becomes hard to maintain once we add:

- BM25
- HybridRAG
- LightRAG
- PathRAG
- more datasets

So the new convention is:

- `evaluation/methods/*.py`: real implementation
- `evaluation/script_*.py`: thin compatibility wrappers

This keeps old commands working while giving the project room to grow.

## Current methods here

- `hypergraphrag.py`
- `swhc.py`
- `graphrag.py`
- `standardrag.py`
- `naivegeneration.py`

## Planned additions

- `bm25.py`
- `hybrid_rag.py`
- `lightrag.py`
- `pathrag.py`

## Rule of thumb

If a new baseline needs its own retrieval logic, put the implementation here first.
Only keep a top-level `script_*.py` wrapper if you want to preserve a short legacy command.
