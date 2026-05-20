# Hypertension No-Judge Baseline Comparison

Updated: `2026-04-18`

## Scope

- Dataset: `hypertension`
- Scoring mode: `LLM judge off`
- Shared generation model: `DeepSeek official API / deepseek-chat`
- Shared default embedding: local `Qwen/Qwen3-Embedding-0.6B`
- `GraphRAG` here refers to the **Microsoft official GraphRAG** baseline

## Fairness Check

This table now keeps only the **current directly comparable six-method runs**.

- `NaiveGeneration / StandardRAG / HybridRAG / GraphRAG / HyperGraphRAG / SWHC` all now satisfy:
  - prompt-side knowledge matches current `test_knowledge.json` for `512 / 512` samples
  - generation errors are `0 / 512`
  - token usage is recorded for `512 / 512` samples
  - Step3 / Step4 use the same shared pipeline
- Earlier historical rows for `StandardRAG`, `NaiveGeneration`, `HyperGraphRAG`, and `SWHC` should now be treated as **legacy reference only**.
  - `StandardRAG` previously had a real prompt/knowledge snapshot mismatch.
  - `NaiveGeneration / HyperGraphRAG / SWHC` previously matched by question key, but not by current row order, so row-wise file inspection and future resume behavior were not fully safe.
- `BM25` is still excluded because its current no-judge file remains a partial lower bound after the earlier `402 Insufficient Balance` interruption.

## Overall Results

| Method | EM | F1 | R-Sim | Avg Context Tokens | Avg Consumed Tokens | Generation Errors | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| NaiveGeneration | 6.05 | 13.93 | 0.00 | 0.0 | 564.80 | 0 | Clean rerun on current shared pipeline |
| StandardRAG | 5.47 | 18.74 | 63.72 | 11520.9 | 12077.44 | 0 | Clean rerun on current Step2 snapshot |
| HybridRAG | 6.64 | 20.94 | 63.81 | 11522.2 | 11999.55 | 0 | `BM25 + Dense` flat baseline |
| GraphRAG | 5.08 | 14.76 | 68.70 | 7269.9 | 8026.14 | 0 | Microsoft official `GraphRAG` + `standard` indexing + `local search` |
| HyperGraphRAG | 4.69 | 19.80 | 66.53 | 21362.7 | 22839.20 | 0 | Clean rerun on current shared pipeline |
| SWHC | 8.01 | 23.73 | 69.33 | 4833.3 | 5416.99 | 0 | Clean rerun on current shared pipeline; current best overall result |

Notes:

- `Avg Context Tokens` measures the average tokenized length of Step2 `knowledge` text.
- `Avg Context Tokens` is aligned across all six methods under the same counting rule.
- `Avg Consumed Tokens` now comes from actual Step3 usage recording for all six rows.
- The current table is therefore the first fully token-comparable six-method `hypertension` no-judge snapshot in this project.

## BM25 Partial Snapshot (Not Official Yet)

The current `BM25` run should be treated as a progress marker rather than a paper-table result:

| Method | Completed Generations | Failed Generations | EM | F1 | R-Sim | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| BM25 | 421 | 91 | 4.69 | 16.57 | 61.80 | Partial lower bound only |

Why it is excluded from the main table:

- the interrupted run stopped at `421 / 512` successful generations
- the remaining `91` samples are currently API error outputs caused by the earlier `402 Insufficient Balance`
- the resulting score is therefore a pessimistic lower bound, not a fair completed baseline
- resume support is already in place, so once balance is restored we should continue from the current generation file instead of rerunning the finished `421` samples

## Main Findings

1. `SWHC` is still the strongest overall method on the current `hypertension` no-judge setting.
   - Compared with the refreshed `HyperGraphRAG`, it improves `EM` by `+3.32`, `F1` by `+3.93`, and `R-Sim` by `+2.80`.
   - Compared with `HybridRAG`, it improves `EM` by `+1.37`, `F1` by `+2.79`, and `R-Sim` by `+5.52`, while using less than half as many consumed tokens (`5416.99` vs `11999.55`).
   - This remains the most important result because `SWHC` changes query-time evidence assembly rather than the indexing build.

2. The refreshed fair table is materially different from the older mixed historical reading.
   - After rerunning `NaiveGeneration / HyperGraphRAG / SWHC` on the same current pipeline, the earlier large `HyperGraphRAG / SWHC` lead shrinks substantially on `EM / F1`.
   - The older `HyperGraphRAG = 34.40 F1` and `SWHC = 37.60 F1` numbers should not be mixed into the current six-method table.
   - Because the generation backend is a remote API service, same-wave reruns are the safer basis for direct comparison.

3. The current ranking on exact-answer quality is now:
   - `SWHC` (`23.73 F1`)
   - `HybridRAG` (`20.94 F1`)
   - `HyperGraphRAG` (`19.80 F1`)
   - `StandardRAG` (`18.74 F1`)
   - `GraphRAG` (`14.76 F1`)
   - `NaiveGeneration` (`13.93 F1`)
   - So `HybridRAG` is now the strongest non-SWHC baseline on `F1`, and `HyperGraphRAG` no longer clearly dominates the flat baselines under the refreshed shared pipeline.

4. `GraphRAG`, `HyperGraphRAG`, and `SWHC` now expose a clearer token-quality tradeoff.
   - `GraphRAG` is the most semantically aligned flat/graph baseline on `R-Sim` except `SWHC`, reaching `68.70` with relatively compact consumed tokens (`8026.14`).
   - `HyperGraphRAG` is now the most expensive baseline in consumed tokens (`22839.20`) but does not beat `HybridRAG` or `SWHC` on `F1`.
   - `SWHC` is the strongest tradeoff among the three structured methods here: it has the best `F1` and `R-Sim`, while consuming far fewer tokens than `HyperGraphRAG`.

5. `NaiveGeneration` confirms that retrieval is necessary.
   - Without retrieval evidence, `EM` and `F1` stay low at `6.05 / 13.93`.
   - This supports the overall experiment direction: the remaining question is not whether retrieval helps, but which retrieval-and-assembly strategy helps most.

## Method-by-Method Reading

### NaiveGeneration

- Useful as the floor baseline.
- Even after a clean rerun, it remains close to the bottom of the table.

### StandardRAG

- It is now a clean dense-chunk reference line on the current snapshot.
- The refreshed result is substantially lower than the earlier historical number, which confirms that the previous `StandardRAG` line was not a fair comparator.

### HybridRAG

- It now has a complete `512 / 512` no-judge run with token recording.
- Relative to `GraphRAG`, it spends more tokens and gets better `EM / F1`, so it currently looks more answer-oriented but less semantically compact.

### GraphRAG

- The official Microsoft implementation is now fully integrated and has completed full `hypertension` no-judge Step1~Step4.
- This line now refers specifically to `Microsoft official GraphRAG + standard indexing + local search`, not the older internal proxy implementation.
- Its current behavior is semantically strong, but still not very answer-extractive on this QA task.
- In the current task setting, it looks more like a compact semantically coherent evidence retriever than a top exact-answer baseline.

### HyperGraphRAG

- The refreshed run is no longer the strongest non-`SWHC` baseline.
- Its remaining strength is semantic quality and graph-structured evidence, but the token cost is now clearly the highest in the table.

### SWHC

- Best overall on all three currently used no-judge metrics in the refreshed fair table.
- Since `SWHC` only changes query-time evidence assembly, this is still useful for the method story: the gain comes from better evidence selection and connection, not from a stronger indexing build.

## Practical Conclusion

For the current `hypertension` no-judge matrix, the most stable reading is:

`SWHC` > `HybridRAG` >= `HyperGraphRAG` >= `StandardRAG` > `GraphRAG` > `NaiveGeneration` on `F1`, while official `GraphRAG` remains strong on semantic relevance and `SWHC` currently offers the best accuracy-cost balance.

This means the current paper narrative can already support two claims:

1. Structured graph / hypergraph retrieval is meaningfully better than retrieval-free generation on this task.
2. Within the structured family, `SWHC` currently gives the best accuracy-quality-cost tradeoff among the methods that have been completed.

## Remaining Caveats

1. This summary is still based on a single dataset: `hypertension`.
2. `BM25` is still missing a complete official no-judge result.
3. The current fair table is generation-model specific: because `DeepSeek official API` is a remote service, later reruns may drift again even if the local code stays fixed.
4. For `GraphRAG`, the current row is already the official Microsoft implementation, while any older `GraphRAG-local` style result should be treated as legacy and not directly compared against this table.
