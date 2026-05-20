# SWHC 规划与实现优先级

更新时间：`2026-04-14`

## 1. 文档目的

这份文档用于固定当前项目的阶段性决策，避免后续实现过程中反复摇摆。它主要回答四个问题：

1. 当前已经做到哪里
2. 当前卡点是什么
3. 最终要比较哪些 baseline、使用哪些数据集
4. 接下来应该按什么顺序实现和复现

这份文档面向后续研发、实验推进和对内同步，不是最终论文文本。

---

## 2. 当前项目目标

项目目标是：在 `HyperGraphRAG` 基础上实现并评估 `SWHC (Semantic Wiener HyperConnector)`，验证它是否能够在**更紧凑的上下文预算**下，提升多跳、n-ary 事实场景中的检索组装质量和最终问答效果。

当前的核心研究命题可以概括为：

> HyperGraphRAG 解决了 n-ary fact 的表示问题，而 SWHC 进一步解决 query-time 的 evidence assembly 问题。

---

## 3. 当前进度总结

## 3.1 代码与系统层面

已经完成：

1. `SWHC` 方法的第一版实现
   - 已接入 `HyperGraphRAG` 的 query-time 主链
   - 支持通过 `QueryParam(subgraph_selector=\"swhc\")` 启动
   - 已完成候选子图、语义加权、初始 connector、bridge augmentation、pruning、上下文化导出

2. `HyperGraphRAG` 与 `SWHC` 的评测入口整理
   - `evaluation/methods/` 已建立统一方法入口
   - 旧的 `script_*.py` 已保留为兼容 wrapper

3. 评测链路已支持双推理后端
   - `realtime`
   - `batch`
   - 目前 Step3/Step4 可以设计成“切开关即切后端”

4. 仓库结构已完成一轮整理
   - `docs/`
   - `evaluation/methods/`
   - `evaluation/logs/`
   - `evaluation/debug/`
   - `logs/archive/`

5. `StandardRAG` 已改为更公平的 dense chunk baseline
   - 不再依赖 `HyperGraphRAG` 先产出的 `Sources`
   - 现在是直接对 `chunks_vdb` 做 dense retrieval

6. 已有一个 `GraphRAG-local` 临时 baseline
   - 用于内部对照和开发验证
   - 但不应替代 official GraphRAG

## 3.2 实验层面

当前已经完整跑通的只有 `hypertension` 数据集上的两种方法：

1. `HyperGraphRAG`
2. `SWHC`

其中当前最重要的已完成结果是：

| Method | EM | F1 | R-Sim | Gen |
| --- | ---: | ---: | ---: | ---: |
| HyperGraphRAG | 21.29 | 34.40 | 66.53 | 55.63 |
| SWHC | 24.41 | 37.60 | 69.33 | 55.67 |
| Delta | +3.12 | +3.20 | +2.81 | +0.04 |

并且：

- `SWHC` 平均上下文 token 从 `21362.7` 降到 `4833.3`
- 压缩约 `77.38%`
- `3-hop` 提升最明显

这说明当前方向已经有支持性结果，值得继续投入。

---

## 4. 当前存在的问题

## 4.1 外部 API 问题

当前最大的外部阻塞不是本地代码，而是远程 API 权限问题。此前已经稳定出现：

- `403 invalid user v2`

影响：

1. 部分 baseline 的 Step3 无法稳定完成
2. Step4 的 LLM judge 评分无法持续跑完
3. 批量推理后端目前也被同一账号/Key 问题挡住

这意味着：

- 本地索引、检索、数据处理链是通的
- 生成与 judge 阶段受上游服务状态影响

## 4.2 baseline 还不完整

当前真正可用于正式比较的 baseline 还不完整：

- `NaiveGeneration`：部分完成
- `StandardRAG`：部分完成
- `GraphRAG-local`：仅内部参考
- `BM25`：未实现
- `Hybrid RAG`：未实现
- `GraphRAG (official)`：未实现
- `LightRAG`：未实现
- `PathRAG`：未实现

## 4.3 数据集仍然太少

当前完整结果只有：

- `hypertension`

这还不足以支撑论文级结论。必须扩展到：

- 当前 HyperGraphRAG 五域 benchmark
- 外部公开 benchmark

## 4.4 official baseline 缺失

尤其需要注意：

- 当前仓库里的 `GraphRAG-local` 只是临时对照
- 正式论文中应以 `GraphRAG (official)` 为准

这个问题如果不提前规划，后期会成为投稿风险。

---

## 5. 今天确认的 baseline 列表

最终 baseline 采用下面这 9 个：

1. `NaiveGeneration`
2. `BM25`
3. `StandardRAG`
4. `Hybrid RAG (BM25 + Dense)`
5. `GraphRAG (official)`
6. `LightRAG`
7. `PathRAG`
8. `HyperGraphRAG`
9. `SWHC`

## 5.1 这组 baseline 的意义

这套 baseline 覆盖了四类对照：

### A. 无检索 / 平坦检索

- `NaiveGeneration`
- `BM25`
- `StandardRAG`
- `Hybrid RAG`

作用：

- 验证结构方法是否真的优于强 flat baseline

### B. 主流 graph baseline

- `GraphRAG (official)`
- `LightRAG`
- `PathRAG`

作用：

- 验证 `SWHC` 是否优于当前主流 graph retrieval / graph assembly 方法

### C. 直接前身方法

- `HyperGraphRAG`

作用：

- 验证 `SWHC` 相比原始超图方法的改进是否成立

### D. 本文方法

- `SWHC`

作用：

- 作为最终目标方法

## 5.2 当前 baseline 状态

| Method | Current Status | Role |
| --- | --- | --- |
| NaiveGeneration | 部分完成 | 下界 |
| BM25 | 未开始 | 纯 lexical baseline |
| StandardRAG | 部分完成 | 纯 dense baseline |
| Hybrid RAG | 未开始 | 强 flat baseline |
| GraphRAG (official) | 未开始 | 经典官方图 baseline |
| LightRAG | 未开始 | 轻量图检索 baseline |
| PathRAG | 未开始 | 路径型图 baseline |
| HyperGraphRAG | 已完成单数据集 | 直接前身 |
| SWHC | 已完成单数据集 | 目标方法 |

---

## 6. 今天确认的数据集列表

最终数据集采用下面这 5 组：

1. 当前 HyperGraphRAG 五域 benchmark
2. `HotpotQA`
3. `2WikiMultiHopQA`
4. `MuSiQue`
5. `PopQA`

## 6.1 各数据集的角色

### A. 当前 HyperGraphRAG 五域 benchmark

包含：

- `hypertension`
- `agriculture`
- `cs`
- `legal`
- `mix`

价值：

- 能直接分析 `1-hop / 2-hop / 3-hop`
- 能直接分析 `binary / n-ary`
- 能验证 SWHC 是否真的更适合 n-ary 事实与多跳场景

这套数据集是**机制分析主轴**，必须保留。

### B. HotpotQA

价值：

- 经典公开多跳 QA benchmark
- 有 supporting facts
- 适合验证跨文档证据组装能力

### C. 2WikiMultiHopQA

价值：

- 多步推理结构更明确
- 适合验证 connector-style evidence assembly

### D. MuSiQue

价值：

- 专门为减少 shortcut 而设计
- 适合应对“方法只是吃 benchmark shortcut”的质疑

### E. PopQA

价值：

- 作为非多跳/弱多跳控制集
- 用于说明 SWHC 的收益主要来自多证据连接，而不是对所有事实性 QA 都无差别提升

## 6.2 为什么强调多跳，但不只做多跳

当前方法最强的故事是：

- 多跳证据连接
- n-ary 事实组装
- 更紧凑的 reasoning-ready context

所以**应该强调多跳数据集**。

但不能只做多跳，因为：

- 只做多跳会让 reviewer 质疑外部有效性
- 需要一个控制集说明方法的适用边界

因此：

- `五域 benchmark + HotpotQA + 2Wiki + MuSiQue` 作为主结果
- `PopQA` 作为控制集

这个组合比较平衡。

---

### 6.3 建议补充的评价指标

除当前已经在用的 `EM / F1 / R-Sim / Gen` 外，后续论文版实验建议补充以下指标：

1. `Supporting Fact Recall / F1`
   - 适用数据集：`HotpotQA`、`2WikiMultiHopQA`、`MuSiQue`
   - 作用：更细粒度地评估检索或组装出的证据是否覆盖黄金 supporting facts，比当前整体文本相似度 `R-Sim` 更直接。

2. `Average Context Tokens`
   - 作用：统计平均上下文长度，正式衡量方法的上下文效率。
   - 对 `SWHC` 尤其重要，因为它的核心卖点之一就是“在更小上下文下保持或提升效果”。

3. `F1 per Token`
   - 作用：衡量单位上下文预算带来的答案收益，可直接支持“更高上下文利用率”的论点。
   - 可简单定义为：`overall_f1 / avg_context_tokens`，或统一缩放到每千 token。

4. `Terminal / Source 数量`
   - 作用：从结构层面衡量子图规模。
   - `Terminal` 数量可以反映 query-time 关键节点的保留规模；`Source` 数量可以反映最终回传给 LLM 的原始证据片段规模。
   - 这组指标特别适合用来支撑 `SWHC` 的“更紧凑 evidence assembly”故事。

这些指标的定位是：

- `EM / F1 / Gen`：答案质量
- `Supporting Fact Recall / F1`、`R-Sim`：证据质量
- `Average Context Tokens`、`F1 per Token`、`Terminal / Source 数量`：上下文效率与结构紧凑性

## 7. 实现与复现优先级

下面按优先级排序，而不是按论文名称排序。

## P0：立刻推进

### 方法

1. `BM25`
2. `Hybrid RAG (BM25 + Dense)`
3. 补齐 `NaiveGeneration`
4. 补齐 `StandardRAG`
5. 保持 `HyperGraphRAG`
6. 保持 `SWHC`

### 原因

- 这是最快能补齐的 flat baseline 组
- 能最快减少审稿风险
- 也是当前最容易在现有评测链上接起来的一组

### 交付目标

先在 `hypertension` 上形成一张 6 方法表：

- `NaiveGeneration`
- `BM25`
- `StandardRAG`
- `Hybrid RAG`
- `HyperGraphRAG`
- `SWHC`

---

## P1：补主流 graph baseline

### 方法

1. `LightRAG`
2. `GraphRAG (official)`

### 原因

- 这是最关键的 graph baseline 对照
- `LightRAG` 通常更容易先落地
- `GraphRAG official` 必须有，但实现和配置成本更高

### 交付目标

在 `hypertension` 上把主表扩成 8 方法。

---

## P2：最后补路径型 baseline

### 方法

1. `PathRAG`

### 原因

- 它和 `SWHC` 的研究问题最接近
- 但适配成本最高
- 应该在前面主表已经成型后再做

### 交付目标

形成完整 9 方法主表。

---

## 8. 数据集推进优先级

## P0：先在 `hypertension` 跑通所有方法

目标：

- 统一实验链
- 统一结果格式
- 统一比较表

这一步的产物是“内部主表”。

## P1：补齐当前五域 benchmark

顺序建议：

1. `agriculture`
2. `cs`
3. `legal`
4. `mix`

原因：

- 这套数据最容易复用当前评测链
- 能最快做 `binary / n-ary / hop` 分析

## P2：公开多跳 benchmark

顺序建议：

1. `HotpotQA`
2. `2WikiMultiHopQA`
3. `MuSiQue`

原因：

- 这三套数据是最关键的公开多跳证据
- 也是最能支撑“多跳证据组装”故事的一组

## P3：控制集

1. `PopQA`

原因：

- 用于控制“非多跳场景”
- 用来界定 SWHC 的适用边界

---

## 9. 建议的阶段性执行计划

## 阶段 1：补齐 flat baseline

优先完成：

1. `BM25`
2. `Hybrid RAG`
3. `NaiveGeneration`
4. `StandardRAG`

目标：

- 在 `hypertension` 上形成第一张可投递的内部主表

## 阶段 2：补齐 graph baseline

优先完成：

1. `LightRAG`
2. `GraphRAG (official)`

目标：

- 把主表从“内部对照”升级为“有论文说服力的对照”

## 阶段 3：补 `PathRAG`

目标：

- 完成路径型 graph method 对照
- 增强与 `SWHC` 最接近方法的比较

## 阶段 4：扩展到更多数据集

目标：

1. 补齐当前五域 benchmark
2. 再扩到 `HotpotQA / 2Wiki / MuSiQue / PopQA`

## 阶段 5：论文表格与分析

需要产出：

1. 主表
2. `Binary / N-ary` 分表
3. `1-hop / 2-hop / 3-hop` 分表
4. 上下文规模表
5. 运行成本表
6. case study
7. ablation

---

## 10. 当前最重要的风险

1. 远程 API 仍可能继续阻塞 Step3/Step4
2. official GraphRAG 适配成本可能高于预期
3. PathRAG 可能更像完整系统，而不是最小 benchmark pipeline
4. 当前结论仍然建立在单数据集上，不能过度外推

---

## 11. 近期最值得做的事

如果只看接下来最有价值的工作，建议顺序如下：

1. 实现 `BM25`
2. 实现 `Hybrid RAG`
3. 补齐 `NaiveGeneration / StandardRAG` 的 Step4~Step5
4. 跑完 `agriculture / cs / legal / mix`
5. 开始接 `LightRAG`
6. 开始接 `GraphRAG (official)`

---

## 12. 当前项目一句话状态

> `SWHC` 已经在 `hypertension` 上证明了“更紧凑的证据子图组装”是有效方向；当前的主要任务不是再验证方向本身，而是尽快补齐 baseline 和数据集，把支持性结果扩展成正式论文级证据链。
