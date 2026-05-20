# HotPotQA_64 No-Judge Baseline Comparison

Updated: `2026-05-06`

Note: the main six-method table below is the original `2026-05-05` pilot snapshot. The `2026-05-06` update appends SWHC-only diagnostics and a six-method shortest-answer rerun. Treat prompt variants as separate evaluation protocols.

## Scope

- Dataset: `hotpotqa_64`
- Source: Hugging Face `hotpotqa/hotpot_qa`
- Config / split: `distractor / validation`
- Sample: first `64` rows
- Context conversion: `bundle`
  - one document per QA sample
  - each document contains the sample's provided distractor paragraphs
- Scoring mode: `LLM judge off`
- Shared generation model: `gpt-5.4-mini-hy` via current `api_config.txt`
- HyperGraphRAG embedding: local `Qwen/Qwen3-Embedding-0.6B`
- Official GraphRAG embedding: Ollama OpenAI-compatible `qwen3-embedding:0.6b`
- `GraphRAG` refers to the Microsoft official GraphRAG implementation.

## Fairness Check

All six rows satisfy the current no-judge comparability requirements:

- `64 / 64` generations completed
- `0 / 64` final generation errors
- `64 / 64` generation token-usage records
- shared Step3 / Step4 pipeline
- `LLM judge` disabled

One `NaiveGeneration` sample initially triggered provider `invalid_prompt` filtering. It was regenerated with an explicit benign-benchmark safety preface, and token usage was recorded for the regenerated sample.

## Overall Results

| Method | EM | F1 | R-Sim | Avg Context Tokens | Avg Consumed Tokens | Generation Errors | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| NaiveGeneration | 14.06 | 32.34 | 0.00 | 0.00 | 189.17 | 0 | Retrieval-free floor; one policy false positive regenerated with safety preface |
| StandardRAG | 40.62 | 62.07 | 61.57 | 11467.70 | 11656.72 | 0 | Dense chunk retrieval |
| HybridRAG | 37.50 | 60.94 | 60.28 | 11473.00 | 11661.14 | 0 | `BM25 + Dense` flat retrieval |
| GraphRAG | 35.94 | 55.10 | 68.01 | 5121.73 | 5311.81 | 0 | Microsoft official GraphRAG, standard indexing, local context |
| HyperGraphRAG | 43.75 | 66.56 | 68.38 | 17347.72 | 17531.95 | 0 | Highest EM/F1, highest answer-generation token use |
| SWHC | 39.06 | 61.20 | 67.30 | 2844.41 | 3036.39 | 0 | Most compact structured method; not the top F1 row on this pilot |

## Build / Index Notes

HyperGraphRAG Step1 completed under `gpt-5.4-mini-hy` without using a fallback model:

- documents: `64`
- chunks: `120`
- graph nodes: `10433`
- graph edges: `10195`

Official GraphRAG indexing completed after adding a content-filter robustness patch in the integration layer:

- documents: `64`
- text units: `110`
- entities: `4158`
- relationships: `4204`
- communities: `571`
- community reports: `571`
- successful final workflow set: `create_base_text_units`, `create_final_documents`, `extract_graph`, `finalize_graph`, `extract_covariates`, `create_communities`, `create_final_text_units`, `create_community_reports`, `generate_text_embeddings`

The unpatched official GraphRAG run failed during `extract_graph` because one `gpt-5.4-mini-hy` description-summary prompt was rejected by provider content filtering. The patch keeps normal model calls unchanged and only falls back to deterministic local description concatenation/truncation for the filtered summary.

Recorded successful official GraphRAG indexing usage:

- chat model responses: `2046`
- chat cache hits: `1079`
- chat total tokens: about `3,872,004`
- local embedding responses: `333`
- local embedding prompt tokens: about `773,009`

## Main Findings

1. `HyperGraphRAG` is the strongest exact-answer row on this pilot.
   - It leads on EM and F1: `43.75 / 66.56`.
   - The cost is high: `17531.95` average consumed tokens, the largest in the table.

2. `SWHC` is very token efficient but not the top answer-quality row here.
   - It reaches `61.20` F1 and `67.30` R-Sim with only `3036.39` average consumed tokens.
   - Compared with `HyperGraphRAG`, it loses `5.36` F1 but uses about `17%` of the answer-generation tokens.
   - This differs from the `hypertension` table, where `SWHC` is the best overall row.

3. Flat retrieval is unusually competitive under `bundle` conversion.
   - `StandardRAG` and `HybridRAG` both exceed `60` F1.
   - In `bundle` mode, each QA sample's distractor context is kept together as one document, so dense retrieval can often retrieve a near-complete evidence bundle.
   - This setting is useful as a smoke test, but may be generous to flat chunk retrieval.

4. Official `GraphRAG` is compact and semantically strong, but lower on exact answers.
   - It has `68.01` R-Sim with much lower answer-generation tokens than `HyperGraphRAG`.
   - Its F1 is lower than `StandardRAG`, `HybridRAG`, `HyperGraphRAG`, and `SWHC`.

5. `NaiveGeneration` is not a trivial baseline on HotPotQA_64.
   - It gets `32.34` F1 from model prior alone.
   - Retrieval still matters substantially: every retrieval method improves over it by at least `22.76` F1 points.

## SWHC Follow-Up Diagnostics

After the initial table, two SWHC-only diagnostics were run on `2026-05-06` to understand why SWHC trailed HyperGraphRAG on raw EM/F1 while remaining much more compact.

These runs should be read as ablations, not as directly comparable replacements for the original six-method table.

### Source Rerank Diagnostic

An answer-aware / question-aware source rerank was implemented at SWHC context export time. It keeps the selected SWHC connector subgraph fixed, then changes only the ordering of the exported `Sources` using a weighted score over:

- structural source support
- query/source lexical overlap
- terminal coverage
- selected-node score support
- length penalty

This does not change indexing, entity extraction, hyperedge construction, or the SWHC connector solver. It does change query-time context assembly, so pre-rerank and post-rerank SWHC rows are not directly comparable without qualification.

Default going forward: source rerank is disabled for normal SWHC runs. Enable it only for an explicitly labeled ablation with `HGRAG_SWHC_SOURCE_RERANK=true`; routine future notes do not need to restate this default.

| SWHC Variant | EM | F1 | R-Sim | Avg Consumed Tokens | Support Sentence Recall | Full-Support Samples | Avg Sources | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Pre-rerank baseline | 39.06 | 61.20 | 67.30 | 3036.39 | 127 / 158 | 41 / 64 | 2.53 | Original SWHC pilot reading |
| Source rerank enabled | 37.50 | 59.93 | 66.72 | 3047.95 | 128 / 158 | 42 / 64 | 2.58 | Slightly better retrieval coverage, but lower answer metrics |

Interpretation:

- Source rerank gave a very small retrieval-side improvement: `+1` supporting sentence and `+1` full-support sample.
- It did not improve no-judge answer quality; EM/F1/R-Sim all dropped slightly.
- This suggests that merely reordering the small set of already selected SWHC sources is not enough. If source-side retrieval is the target, the next useful step is likely source expansion around the selected subgraph, not only source reranking.
- Source rerank is therefore kept as an ablation option, not the default for the current HotPotQA direction.

### Shortest-Answer Prompt Diagnostic

A separate generation-side diagnostic tested whether SWHC's HotPotQA EM/F1 loss was partly caused by verbose final answers. The experiment used source rerank disabled and compared two generation prompts on the same no-rerank `test_knowledge.json`:

- normal prompt: original answer instruction
- shortest-span prompt: `<answer>` must contain only the shortest final answer span, such as `yes`, `2000`, `Fujioka, Gunma`, or a comma-separated list

The retrieval context was the same for both rows:

- support-sentence recall: `127 / 158`
- full-support samples: `41 / 64`
- average sources: `2.59`
- average entities: `4.75`
- average relationships: `4.61`

| SWHC Generation Prompt | EM | F1 | R-Sim | Avg Consumed Tokens | Avg Answer Words | Generation Errors | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Normal prompt, same no-rerank knowledge | 39.06 | 59.38 | 67.01 | 3110.92 | 6.14 | 0 | Verbose `<answer>` often includes full explanatory sentences |
| Shortest-span prompt, same no-rerank knowledge | 75.00 | 85.42 | 67.01 | 3183.22 | 2.31 | 0 | Strong answer-format correction |

Pairwise same-knowledge comparison:

- shortest-span prompt wins on F1 for `28 / 64` samples
- loses on F1 for `3 / 64` samples
- ties on `33 / 64` samples
- average per-sample F1 delta: `+0.2605`
- EM improves by `+23` samples

Examples where shortest-span prompting fixed the metric:

| Question Type | Gold | Normal Prompt Answer | Shortest-Span Answer |
| --- | --- | --- | --- |
| yes/no comparison | `yes` | `Yes. Both Scott Derrickson and Ed Wood were American.` | `yes` |
| date/year | `2000` | `Poison's album ... was released on March 14, 2000.` | `2000` |
| location | `Fujioka, Gunma` | `Buck-Tick hails from Japan.` | `Fujioka, Gunma` |
| list | `Max Martin, Savan Kotecha and Ilya Salmanzadeh` | longer, partly wrong writer list | `Max Martin, Savan Kotecha and Ilya Salmanzadeh` |

There were also a few regressions. For example, for a question whose gold answer is the descriptive phrase `Organizations could come together to address global issues`, the shortest-span prompt returned `World Summit of Nobel Peace Laureates`, which is a related entity but not the expected answer phrase.

Interpretation:

- A large part of SWHC's apparent exact-answer deficit on this pilot is answer-format / verbosity, not retrieval alone.
- R-Sim is unchanged in the same-knowledge prompt diagnostic because R-Sim measures gold support context against retrieved `knowledge`, not generated answer text.
- The shortest-span instruction is a generation-side evaluation protocol change. It should be applied consistently to all methods before producing a fair cross-method table.
- This diagnostic does not remove the need to improve SWHC retrieval: some low-F1 cases still miss key second-hop evidence.

### Six-Method Shortest-Answer Rerun

On `2026-05-06`, all six methods were regenerated and rescored with `HGRAG_SHORTEST_ANSWER_SPAN=true`.

Only Step3 and Step4 were rerun:

- existing `test_knowledge.json` files were reused
- no indexing or retrieval rerun
- `SWHC` used the default no-rerank setting
- LLM judge remained disabled
- final generation errors: `0 / 64` for every method
- token usage records: `64 / 64` for every method

| Method | EM | F1 | R-Sim | Avg Consumed Tokens | Avg Answer Words | Delta EM vs Original | Delta F1 vs Original |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| NaiveGeneration | 37.50 | 51.35 | 0.00 | 262.48 | 2.12 | +23.44 | +19.01 |
| StandardRAG | 71.88 | 84.56 | 61.57 | 11735.27 | 2.33 | +31.26 | +22.49 |
| HybridRAG | 71.88 | 86.40 | 60.28 | 11740.41 | 2.31 | +34.38 | +25.46 |
| GraphRAG | 59.38 | 72.84 | 68.01 | 5390.42 | 2.30 | +23.44 | +17.74 |
| HyperGraphRAG | 68.75 | 87.24 | 68.38 | 17610.14 | 2.33 | +25.00 | +20.68 |
| SWHC | 71.88 | 83.34 | 67.01 | 3184.52 | 2.39 | +32.81 | +22.14 |

Interpretation:

- The original six-method prompt was shared, but it was not strict enough for HotPotQA exact-span scoring.
- The shortest-answer protocol raises EM/F1 for every method, including retrieval-free `NaiveGeneration`; answer formatting was a major confound in the original table.
- `HyperGraphRAG` remains the best F1 row at `87.24`, but it uses the largest context: about `17610` consumed tokens per sample.
- `SWHC` ties `StandardRAG` and `HybridRAG` on EM at `71.88`, trails `StandardRAG` by only `1.22` F1 points, and uses about `27%` of the `StandardRAG` / `HybridRAG` tokens.
- Against `HyperGraphRAG`, `SWHC` has higher EM by `3.12` points but lower F1 by `3.90` points, while using about `18%` of the tokens.
- `GraphRAG` has strong R-Sim but weaker EM/F1, confirming that support-context similarity alone does not guarantee exact answer extraction.
- Remaining `SWHC` misses are mostly retrieval / specificity misses, not answer-format misses. Examples include returning `Japan` instead of `Fujioka, Gunma`, `1923` instead of `October 1922`, and `Lyndon Johnson` instead of `Nelson Rockefeller`.

### SWHC Error Diagnosis After Shortest-Answer Control

The active `SWHC` result directory after the six-method shortest-answer rerun is:

- `evaluation/results/SWHC/hotpotqa_64/test_knowledge.json`
- `evaluation/results/SWHC/hotpotqa_64/test_generation.json`
- `evaluation/results/SWHC/hotpotqa_64/test_result.json`
- `evaluation/results/SWHC/hotpotqa_64/test_score.json`

Current active SWHC score:

- `EM = 71.88`
- `F1 = 83.34`
- `R-Sim = 67.01`
- average consumed tokens `3184.52`

The main issue is not that the answer is usually absent from the retrieved text. The answer is often present in `Sources`, but it is not explicitly lifted into the structured `Entities` / `Relationships` blocks.

| Diagnostic | Count |
| --- | ---: |
| EM hits | 46 / 64 |
| non-EM samples | 18 / 64 |
| support-sentence recall | 127 / 158 |
| full-support samples | 41 / 64 |
| gold answer appears anywhere in SWHC knowledge | 59 / 64 |
| non-EM samples where gold appears in `Sources` | 18 / 18 |
| non-EM samples where gold appears in `Entities` | 2 / 18 |
| non-EM samples where gold appears in `Relationships` | 4 / 18 |
| zero-F1 hard errors | 8 / 64 |
| zero-F1 hard errors where gold appears in `Sources` | 8 / 8 |
| zero-F1 hard errors where gold appears in `Relationships` | 1 / 8 |

Reading:

- `Sources` are the original textual evidence. They often contain the correct answer span.
- `Entities` are extracted entity or concept nodes. They summarize salient objects but do not necessarily include the final answer.
- `Relationships` are the selected hyperedges / structured facts connecting entities. They are compact and visually authoritative, but can omit precise answer attributes.

This creates a generation-side failure mode: the LLM sees all three blocks, but `Entities` and `Relationships` appear earlier and more structured than `Sources`. If the structured part omits the exact answer or emphasizes a nearby wrong slot, the model may follow that stronger structural signal even when the correct answer is present in `Sources`.

Examples:

| Sample | Gold | SWHC Answer | Diagnosis |
| --- | --- | --- | --- |
| `#1` | `Chief of Protocol` | `United States ambassador to Ghana` | Source sentence contains both positions; structured part connects `Kiss and Tell` / `Corliss Archer` but does not lift the exact office. |
| `#15` | `9,984` | `331 million` | Source contains Brown County population, but structure emphasizes country-level `United States`, so the model answers from outside/general population knowledge. |
| `#31` | `Fujioka, Gunma` | `Japan` | Source contains the exact formation place, but the answer collapses to a coarser country-level span. |
| `#35` | `October 1922` | `1923` | Source contains both `October 1922` and a later `1923` statement; the model chooses the wrong temporal interpretation. |
| `#44` | `Nelson Rockefeller` | `Lyndon Johnson` | Source contains the Rockefeller committee, but another committee with `Vice President Lyndon Johnson` creates a competing structured cue. |
| `#54` | `Max Martin, Savan Kotecha and Ilya Salmanzadeh` | `Jim Eliot, Starsmith, Billboard, Justin Parker, MONSTA, Madeon, Mike Spencer` | Correct writer sentence appears in source, but the structured hyperedge highlights producers from a nearby album-related sentence. |
| `#61` | `Ronald Shusett` | `Francis Ford Coppola` | Correct source sentence says `Shusett was executive producer`, but competing film-score evidence makes another executive producer more salient. |

Additional pattern:

- Several non-EM cases are boundary or alias issues rather than real retrieval failures:
  - `3,677` vs `3,677 seated`
  - `1986 to 2013` vs `from 1986 to 2013`
  - `Lee Hazlewood` vs `Barton Lee Hazlewood`
  - `Mumbai, Maharashtra` vs `Mumbai`
  - `Virginia Woolf` vs `Adeline Virginia Woolf`

Current problem statement:

- SWHC is compact and usually retrieves a source containing the answer.
- However, the answer span often remains buried in the source text.
- The structured blocks do not reliably expose answer candidates or precise answer attributes.
- Source bundles can contain multiple nearby candidate answers, making slot selection fragile.
- The remaining SWHC loss is therefore mainly evidence organization and answer-candidate exposure, not raw prompt verbosity.

Recommended next direction:

- Keep source rerank disabled by default.
- Add query-aware evidence compression / sentence extraction over already selected SWHC sources.
- Surface a short `Relevant Evidence` block before `Entities` / `Relationships` / `Sources`.
- Prefer sentence windows that contain query terminals, bridge entities, selected entity aliases, numbers, dates, places, people, organizations, titles, and other answer-like spans.
- Optionally add lightweight answer-candidate spans beside selected sources, without changing indexing or the SWHC connector solver.

## Practical Reading

For this pilot:

`HyperGraphRAG` > `StandardRAG` > `SWHC` > `HybridRAG` > `GraphRAG` > `NaiveGeneration` on F1.

The main research signal is not the same as the `hypertension` snapshot. `SWHC` remains the most compact structured method, but `HyperGraphRAG` wins raw EM/F1 on this small `bundle` HotPotQA setting. Before treating this as a paper-level result, run either a larger `HotPotQA` sample or a stricter title-level corpus construction.

After the follow-up diagnostics, the practical reading is sharper:

- The original six-method table is valid as a shared-pipeline pilot, but its EM/F1 comparison is sensitive to final-answer formatting.
- SWHC's compact retrieval is not the only reason it trails HyperGraphRAG in the original table; the normal prompt often lets the model place explanatory prose inside `<answer>`, which strict EM/F1 penalizes heavily.
- A fair next table should either use the shortest-answer-span instruction for every method or explicitly report that the answer prompt is verbose-friendly and therefore underestimates exact-span performance.
- The six-method shortest-answer rerun is now the cleaner HotPotQA_64 answer-format-controlled comparison.
- Source rerank alone is not currently a strong improvement path; source expansion or better terminal/source coverage is more promising for retrieval-side gains.
- The current SWHC bottleneck is more precise than "retrieval is bad": answers often exist in `Sources`, but are not promoted into answer-candidate evidence that the generator reliably follows.

## Caveats

1. This is a `64`-sample pilot, not a final HotPotQA result.
2. The `bundle` corpus construction is intentionally compact and may be easier than title-level retrieval.
3. Results use `gpt-5.4-mini-hy`; they should not be mixed with the `2026-04-18` `hypertension` table, which used DeepSeek official API / `deepseek-chat`.
4. The official GraphRAG content-filter patch changes robustness behavior for rejected summary prompts. It does not change the model or use a fallback model, but it should be reported with this run.
5. The SWHC source-rerank diagnostic changes query-time context assembly and is not directly comparable to the original pre-rerank SWHC row.
6. The SWHC shortest-answer diagnostic changes the generation prompt only. It should not be compared against other methods unless the same answer-format instruction is applied to them.
7. The six-method shortest-answer rerun applies that instruction consistently across all methods, but it is still a separate protocol from the original `2026-05-05` table.
8. No `SWHC` connector formula, semantic edge weighting, indexing, or solver behavior was changed.
