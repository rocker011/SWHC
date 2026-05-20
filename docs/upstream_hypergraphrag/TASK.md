# TASK.md

Last updated: `2026-05-06`

## Current phase
We are in the **research TODO refinement + paper-facing method strengthening** phase.

## Status snapshot
- baseline implementation for the current main stack is complete
- the current fair no-judge `hypertension` matrix is available for:
  - `NaiveGeneration`
  - `StandardRAG`
  - `HybridRAG`
  - `GraphRAG`
  - `HyperGraphRAG`
  - `SWHC`
- official `GraphRAG` is already integrated into the shared evaluation chain
- first public-dataset pilot is complete on `hotpotqa_64`:
  - source: `hotpotqa/hotpot_qa`, `distractor / validation`
  - sample: first `64` rows
  - context mode: `bundle`
  - six-method no-judge table completed under current `api_config.txt` / `gpt-5.4-mini-hy`
  - `0 / 64` generation errors and `64 / 64` token-usage records for every method
- SWHC source rerank has been implemented after the `hotpotqa_64` fairness analysis:
  - only changes query-time `Sources` ordering after the SWHC subgraph is selected
  - does not change indexing, entity extraction, hyperedge construction, or the connector solver
  - first post-rerank `hotpotqa_64` no-judge SWHC rerun is complete:
    - `EM = 37.50`
    - `F1 = 59.93`
    - `R-Sim = 66.72`
    - average consumed tokens `3047.95`
    - support-sentence recall improved slightly from `127 / 158` to `128 / 158`, but final answer metrics did not improve
- SWHC shortest-answer-span prompt diagnostic is complete on `hotpotqa_64` with source rerank disabled:
  - same no-rerank `test_knowledge.json`
  - normal prompt:
    - `EM = 39.06`
    - `F1 = 59.38`
  - shortest-span prompt:
    - `EM = 75.00`
    - `F1 = 85.42`
  - interpretation:
    - a large share of the apparent SWHC exact-answer gap on HotPotQA_64 is answer-format / verbosity, not retrieval alone
    - if this prompt is used in a fair table, it must be applied consistently to all methods
- six-method shortest-answer-span rerun is complete on `hotpotqa_64`:
  - only Step3/Step4 were rerun; existing `test_knowledge.json` files were reused
  - `SWHC` used default no-rerank
  - all methods have `0 / 64` generation errors and `64 / 64` token-usage records
  - answer-format-controlled no-judge results:
    - `NaiveGeneration`: `EM = 37.50`, `F1 = 51.35`, tokens `262.48`
    - `StandardRAG`: `EM = 71.88`, `F1 = 84.56`, tokens `11735.27`
    - `HybridRAG`: `EM = 71.88`, `F1 = 86.40`, tokens `11740.41`
    - `GraphRAG`: `EM = 59.38`, `F1 = 72.84`, tokens `5390.42`
    - `HyperGraphRAG`: `EM = 68.75`, `F1 = 87.24`, tokens `17610.14`
    - `SWHC`: `EM = 71.88`, `F1 = 83.34`, tokens `3184.52`
  - interpretation:
    - shortest-answer prompting is a separate evaluation protocol and should not be mixed with the original normal-prompt table
    - SWHC is now close to StandardRAG / HybridRAG in answer metrics while using much less context
    - remaining SWHC misses are mostly retrieval / specificity misses, not answer-format misses
- current SWHC error diagnosis after shortest-answer control:
  - `18 / 64` SWHC samples are non-EM under the active shortest-answer run
  - in those `18` non-EM samples, the gold answer appears in `Sources` for `18 / 18`, but only in `Entities` for `2 / 18` and `Relationships` for `4 / 18`
  - in the `8` zero-F1 hard errors, gold appears in `Sources` for `8 / 8`, but in `Relationships` for only `1 / 8`
  - conclusion:
    - SWHC often retrieves text containing the answer, but the answer remains buried in source text instead of being lifted into structured evidence
    - the generator can be pulled toward stronger-looking but incomplete `Entities` / `Relationships` signals
    - next retrieval-side work should prioritize query-aware evidence compression / answer-candidate exposure over source rerank
- `BM25` still only has a partial lower-bound no-judge result after the earlier `402 Insufficient Balance`
  - treat it as a maintenance item, not the current main task
- the current comparison note lives at:
  - `docs/results/hypertension_no_judge_comparison_2026-04-18.md`
  - `docs/results/hotpotqa_64_no_judge_comparison_2026-05-05.md`

## Goal
Use the completed baseline stack to answer the remaining **method-design and paper-story** questions around `SWHC`, instead of continuing baseline plumbing work.

## Stable reference point
- treat the current six-method `hypertension` no-judge table as the default reference snapshot
- keep `SWHC` as a **query-time evidence assembly** method on top of `HyperGraphRAG`
- keep API / model defaults sourced from `api_config.txt`
- current verified remote API base: `https://ai.butel.com/api`
- current verified main chat model: `gpt-5.4-mini-hy`
- by default, judge model follows the same configured chat model unless `HGRAG_JUDGE_MODEL` overrides it
- keep local `Qwen/Qwen3-Embedding-0.6B` as the default embedding
- keep `LLM judge` off for intermediate work unless a task explicitly requires it

If a task changes the `SWHC` formula, semantic weighting, objective, or solver behavior, say explicitly that older `SWHC` results may no longer be directly comparable.
Source rerank is now a disabled-by-default ablation option. Normal future `SWHC` runs should be no-rerank unless the task explicitly requests `HGRAG_SWHC_SOURCE_RERANK=true`; do not repeat this decision in routine experiment notes.
If a task explicitly reruns `SWHC` with source rerank enabled, say that older pre-rerank `SWHC` result rows are not directly comparable to the new row without qualification.

## Active priorities
### P0
1. Formula refinement:
   - decide how to handle baseline methods that do not naturally expose edge confidence `conf` in cross-method comparisons
   - clarify whether `SWHC`-specific confidence should be removed, approximated, or replaced

2. Formula refinement:
   - test replacing token-count cost with the number of retrieved entities
   - or provide a stronger justification for the constant `256` in the current token-cost normalization

3. Method strengthening:
   - prepare a cleaner answer to: why optimize on top of **HyperGraphRAG** instead of standard **GraphRAG**
   - make the method story more defensible in paper writing

4. Method strengthening:
   - discuss how to make the method more genuinely hypergraph-aware
   - especially revisit distance design between entity nodes and hyperedge nodes

### P1
5. Research evaluation expansion:
   - compare against stronger and newer GraphRAG-style baselines only if they are needed for the paper story
   - prioritize targeted comparisons over broad baseline integration work

6. Dataset expansion:
   - `hotpotqa_64` pilot is complete; use it as the current public-dataset smoke result, not a final full-scale table
   - finish the remaining planned datasets
   - extend the comparison beyond the current `hypertension` focus
   - move toward:
     - full / larger `HotpotQA`
     - `2WikiMultiHopQA`
     - `MuSiQue`
     - `PopQA`

### Maintenance only
7. `BM25` completion:
   - resume the interrupted `BM25` no-judge run only if an official table still needs it
   - do not let this block current research TODO work

## Working rules for this phase
- Do not reopen completed baseline implementation work unless it is necessary for a specific research question
- Prefer analysis, ablation, and targeted reruns over broad expensive reruns
- Keep comparisons fair across methods and datasets
- Do not silently change preprocessing, evaluation definitions, dataset splits, or scoring behavior
- Intermediate experiments should still default to `LLM judge off`
- When a research change may invalidate older results, say so before proceeding

## Working defaults
### Runtime
- API / model defaults: read from `api_config.txt`
- Current verified API base: `https://ai.butel.com/api`
- Current verified main model: `gpt-5.4-mini-hy`
- Judge model: by default follows `api_config.txt`; override with `HGRAG_JUDGE_MODEL` if a separate judge is needed
- Embedding: local `Qwen/Qwen3-Embedding-0.6B`

### Scoring
For intermediate experiments:
- `HGRAG_ENABLE_LLM_JUDGE=false`

### SWHC defaults
Treat the following as the current `SWHC` reference setup:

- $\alpha = 1.0$
- $\beta = 0.15$
- $\gamma = 0.05$
- $\varepsilon = 0.05$
- $c_{\text{hop}} = 0.25$
- source rerank:
  - implemented but disabled by default
  - normal future `SWHC` runs should leave it off
  - can be enabled only for explicit ablation with `HGRAG_SWHC_SOURCE_RERANK=true`
  - source score combines structural support, query/source lexical overlap, terminal coverage, node-score support, and length penalty

## Checks
Typical no-judge scoring command:

```powershell
cd /d D:\PythonProjects\HyperGraphRAG\evaluation
set HGRAG_ENABLE_LLM_JUDGE=false
python get_score.py --data_source <dataset> --method <method> --enable_llm_judge false
```

Typical resume-friendly generation command:

```powershell
cd /d D:\PythonProjects\HyperGraphRAG\evaluation
set HGRAG_GENERATION_WORKERS=4
set HGRAG_OPENAI_TIMEOUT_SECONDS=180
python get_generation.py --data_sources <dataset> --methods <method>
```

Behavior note:
- if `results/<Method>/<dataset>/test_generation.json` already exists, `get_generation.py` now skips successful samples and only regenerates missing or `[ERROR]` samples
- Step3 writes `generation_usage` plus flattened consumed-token fields when the backend returns usage
- Step4 writes `avg_consumed_tokens` to `test_score.json`
- because `GraphRAG` now points to the official Microsoft implementation, older internal `GraphRAG-local` style outputs are legacy results and not directly comparable
- on `hotpotqa_64`, official `GraphRAG` with `gpt-5.4-mini-hy` needed a content-filter robustness patch in the integration layer:
  - if a description/community summary prompt is rejected by provider content policy, the integration falls back to deterministic local description concatenation/truncation for that one summary
  - this does not change the chat model or use a fallback model, but should be noted when comparing official `GraphRAG` indexing runs
