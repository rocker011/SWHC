# 当前实验结果与分析

更新时间：`2026-04-14`

## 1. 当前实验范围

目前已经拿到**完整可复现实验结果**的数据集是 `hypertension`。  
当前真正完成 `Step1~Step5` 的方法只有两条：

- `HyperGraphRAG`
- `SWHC`

其他 baseline 还处于部分完成状态，主要受远程生成与评测 API 阻塞影响。因此，这份文档把：

- 已完整跑通的结果
- 当前实验进度
- 可展示的中间结果

分开汇报，避免后续讲解时混淆“正式结论”和“临时状态”。

## 2. 数据集与索引规模

- 数据集：`hypertension`
- 原始文档数：`107`
- chunks：`225`
- entity vectors：`10851`
- hyperedge vectors：`5067`
- 图节点：`15918`
- 图边：`19951`
- 评测问题数：`512`
- Binary：`256`
- N-ary：`256`

## 3. 计划 baseline 的当前状态

| Planned Method | Current Status | Notes |
| --- | --- | --- |
| NaiveGeneration | Step3 complete | 已生成，但未完成 Step4~Step5 |
| BM25 | Not started | 计划中的 flat baseline |
| StandardRAG | Step3 partial | dense chunk baseline，`363/512` 条生成成功 |
| Hybrid RAG (BM25 + Dense) | Not started | 计划中的强 flat baseline |
| GraphRAG (official) | Not started | 当前仓库里只有临时的 `GraphRAG-local` 实现 |
| LightRAG | Not started | 计划中的图 baseline |
| PathRAG | Not started | 计划中的路径型 graph baseline |
| HyperGraphRAG | Complete | `hypertension` 的 Step1~Step5 已完成 |
| SWHC | Complete | `hypertension` 的 Step2~Step5 已完成 |

说明：

- 当前仓库中已经有一个 `GraphRAG-local` 临时实现，可用于内部调试和早期对照。
- 但它**不能替代 official GraphRAG**，后续论文主表里应以 official GraphRAG 为准。

## 4. 已完整跑通的方法结果

| Method | EM | F1 | R-Sim | Gen | Avg Tokens | Avg Entities | Avg Relations | Avg Sources |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HyperGraphRAG | 21.29 | 34.40 | 66.53 | 55.63 | 21362.7 | 107.59 | 101.08 | 6.88 |
| SWHC | 24.41 | 37.60 | 69.33 | 55.67 | 4833.3 | 10.16 | 5.57 | 3.76 |
| Delta (SWHC - HGRAG) | +3.12 | +3.20 | +2.81 | +0.04 | -16529.4 | -97.43 | -95.51 | -3.12 |

### 关键观察

1. `SWHC` 在 `hypertension` 上整体优于 `HyperGraphRAG`。
   - `EM` 提升 `+3.12`
   - `F1` 提升 `+3.20`
   - `R-Sim` 提升 `+2.81`
   - `Gen` 基本持平

2. `SWHC` 的上下文显著更小。
   - 平均 token 从 `21362.7` 降到 `4833.3`
   - 上下文压缩约 `77.38%`

3. 这说明 `SWHC` 的提升不是靠“给模型喂更多内容”，而是在更小的上下文下，把检索到的证据组织得更有效。

![Hypertension overall metrics](/D:/PythonProjects/HyperGraphRAG/docs/figures/results/hypertension_overall_metrics.png)

## 5. 当前已有结果的方法：平均上下文规模

| Method | Avg Tokens | Avg Entities | Avg Relations | Avg Sources | Result Completeness |
| --- | ---: | ---: | ---: | ---: | --- |
| NaiveGeneration | 0.0 | 0.00 | 0.00 | 0.00 | 生成完成，未评分 |
| StandardRAG | 11520.9 | 0.00 | 0.00 | 15.47 | 生成部分完成 |
| GraphRAG-local | 10510.5 | 48.50 | 29.04 | 3.68 | 仅检索完成 |
| HyperGraphRAG | 21362.7 | 107.59 | 101.08 | 6.88 | 完整完成 |
| SWHC | 4833.3 | 10.16 | 5.57 | 3.76 | 完整完成 |

### 这张表怎么讲

- `NaiveGeneration` 没有检索上下文，是下界。
- `StandardRAG` 现在是更公平的 dense chunk baseline，只返回文本 `Sources`。
- `GraphRAG-local` 的规模介于 `StandardRAG` 和 `HyperGraphRAG` 之间，符合“局部图检索”的直觉。
- `HyperGraphRAG` 当前是上下文最大的完成方法。
- `SWHC` 在保留结构化证据的同时，把上下文压缩到了一个明显更适合生成的范围。

![Hypertension context overview](/D:/PythonProjects/HyperGraphRAG/docs/figures/results/hypertension_context_overview.png)

## 6. 分 hop 与分 n-ary 结果

### 6.1 按 hop 划分

| Hop | HyperGraphRAG EM | HyperGraphRAG F1 | SWHC EM | SWHC F1 | Delta EM | Delta F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1-hop | 23.83 | 38.52 | 28.52 | 42.25 | +4.69 | +3.73 |
| 2-hop | 20.31 | 32.42 | 17.19 | 31.62 | -3.12 | -0.80 |
| 3-hop | 17.19 | 28.14 | 23.44 | 34.28 | +6.25 | +6.14 |

### 6.2 按 Binary / N-ary 划分

| Split | HyperGraphRAG F1 | HyperGraphRAG R-Sim | SWHC F1 | SWHC R-Sim | Delta F1 | Delta R-Sim |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Binary | 34.60 | 66.22 | 38.73 | 67.92 | +4.13 | +1.70 |
| N-ary | 34.20 | 66.84 | 36.48 | 70.75 | +2.28 | +3.91 |

### 关键分析

1. `3-hop` 是当前最强的支持性结果。
   - `SWHC` 在 `3-hop` 上的 `EM/F1` 提升最大。
   - 这与方法设计非常一致：SWHC 的优势更像“连接事实链”，而不是单纯扩大召回。

2. `1-hop` 也有稳定提升。
   - 说明 SWHC 不是只对长链推理有效。

3. `2-hop` 是当前最值得继续做 case study 的部分。
   - `R-Sim` 提升明显。
   - 但 `EM/F1` 有轻微下降。
   - 合理推测是：子图压缩让证据更聚焦，但在一部分样本上也删掉了对生成仍有帮助的外围上下文。

4. `N-ary` 子集上的 `R-Sim` 提升更明显。
   - 这说明 SWHC 在多实体事实的支持集选择上确实更有效。

![Hypertension breakdown](/D:/PythonProjects/HyperGraphRAG/docs/figures/results/hypertension_breakdown.png)

## 7. 当前部分完成 baseline 的真实情况

### 7.1 生成阶段健康度

| Method | Successful generations | Error generations | Tagged with `<answer>` |
| --- | ---: | ---: | ---: |
| NaiveGeneration | 512 | 0 | 493 |
| StandardRAG | 363 | 149 | 358 |
| GraphRAG-local | 0 | 512 | 0 |

### 7.2 当前阻塞点

当前未完成 baseline 的主要问题不是索引或代码实现，而是外部远程 API 在生成/评分阶段返回访问错误。此前已经稳定观测到的典型报错是：

- `403 invalid user v2`

因此，当前最可靠的实验结论仍应基于：

- `HyperGraphRAG`
- `SWHC`

而不是基于尚未完成打分的 baseline。

## 8. 对外展示时建议怎么讲

如果是给导师、组会或同学展示，建议按下面这条线来讲：

1. `HyperGraphRAG` 已经能表示 n-ary facts，但查询阶段上下文较大、组装方式更偏启发式。
2. `SWHC` 不改建图，只改 query-time 的 evidence assembly。
3. 在 `hypertension` 上，`SWHC` 用更小上下文取得了更高的 `EM/F1/R-Sim`。
4. `3-hop` 提升最明显，这和“connector-style evidence assembly”的故事高度一致。
5. 当前更完整的 baseline 主表还在补齐中，但方法方向已经有支持性结果。

## 9. 当前结论的边界

1. 当前完整结论仍然是**单数据集结果**。
2. `GraphRAG (official)`、`LightRAG`、`PathRAG` 还没有纳入最终可比主表。
3. `BM25` 与 `Hybrid RAG` 还没有接进统一评测链。
4. 因远程 API 权限问题，部分 baseline 还未完成 Step4~Step5。

## 10. 下一步建议

1. 优先补 `BM25` 和 `Hybrid RAG (BM25 + Dense)`。
2. 把 `GraphRAG-local` 从最终主表中剥离，只作为内部调试参考；正式结果用 official GraphRAG 替代。
3. 在 API 恢复后，补齐 `NaiveGeneration`、`StandardRAG` 的 Step4~Step5。
4. 再向 `LightRAG`、`PathRAG` 扩展。
5. 把 `SWHC` 扩到 `agriculture / cs / legal / mix` 四个数据集，验证泛化性。
