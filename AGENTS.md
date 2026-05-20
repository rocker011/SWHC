# AGENTS.md

## 作用范围

本仓库是 `SWHC (Semantic Wiener HyperConnector)` 的独立研究仓库，路径为：

`D:\PythonProjects\SWHC`

原始仓库：

`D:\PythonProjects\HyperGraphRAG`

只作为上游参考和迁移来源。除非用户明确要求，否则不要修改原始 `HyperGraphRAG` 仓库。

## 开始工作时的固定流程

每次新会话开始时：

1. 读本文件 `AGENTS.md`
2. 读 `TASK.md`
3. 如果涉及实验、评测、结果解释，读 `EXPERIMENT_LOG.md`
4. 如需追溯旧项目决策，读：
   - `docs/upstream_hypergraphrag/AGENTS.md`
   - `docs/upstream_hypergraphrag/TASK.md`
   - `docs/upstream_hypergraphrag/EXPERIMENT_LOG.md`

不要因为新建了独立仓库就重新规划一套完全不同的方法路线；本仓库应继承旧仓库中已经验证过的 SWHC 研究脉络。

## 项目目标

本仓库有两层目标：

1. **方法研究**
   - 把 SWHC 从 HyperGraphRAG 里抽离成清晰、可维护、可优化的独立方法实现。
   - 继续优化 query-time evidence assembly。
   - 强化 SWHC 的 hypergraph-aware 方法故事。

2. **论文产出**
   - 保留可复现 baseline、数据集、指标和实验记录。
   - 支持形成一篇围绕 SWHC 的论文。
   - 所有实验比较必须公平、可追溯、可复现。

一句话定位：

> HyperGraphRAG 解决 n-ary fact 的结构表示；SWHC 进一步解决查询阶段如何选择紧凑、语义加权、适合生成的证据子图。

## SWHC 方法边界

SWHC 是 **query-time 证据组装方法**，不是新的索引或建图方法。

默认保持不变的部分：

- 文档加载
- chunk 切分
- 实体抽取
- hyperedge 抽取
- 二部超图构造
- entity / hyperedge / chunk 向量索引

SWHC 改的是查询阶段：

1. 召回 entity seeds 和 hyperedge seeds
2. 选择高优先级 terminals
3. 构造 query-specific candidate subgraph
4. 选择 semantic-weighted connector subgraph
5. 导出 `Entities / Relationships / Sources`

最终给 LLM 的仍然是文本上下文，而不是图对象或向量。

## 当前 SWHC 核心目标函数

对查询 `q`，令：

- `T_q`：terminal 集合
- `H`：最终证据子图
- `pi_q(t)`：terminal 重要性权重
- `d_sem(u,v)`：语义加权最短路距离

Wiener 项：

```text
W_SWHC(H | q) =
sum_{u,v in T_q, u < v} pi_q(u) * pi_q(v) * d_sem(u,v)
```

当前实用目标函数：

```text
J(H | q) =
alpha * W_SWHC(H | q)
+ beta * sum_v (Tok(v) / 256 + 1 - s(v))
+ gamma * |V(H)|
```

语义边代价近似为：

```text
w_sem(i,j) =
max(
  epsilon,
  1 / sqrt(max(conf(i,j), 1))
  + (1 - (s(i) + s(j)) / 2)
  + hop_cost
)
```

当前默认参数：

- `alpha = 1.0`
- `beta = 0.15`
- `gamma = 0.05`
- `edge_weight_floor = 0.05`
- `hop_cost = 0.25`
- `candidate_hops = 2`
- `seed_topk_entity = 8`
- `seed_topk_hyperedge = 8`
- `hard_terminal_topk = 8`
- `budget_nodes = 80`
- `source_rerank = false`

## 方法不变量

除非任务明确要求改变方法，否则必须保持：

1. SWHC 仍是 query-time assembly 方法。
2. 建图、抽取、索引不属于 SWHC 的默认改动范围。
3. 最终输出保持 `Entities / Relationships / Sources` 兼容格式。
4. `swhc/legacy/` 是迁移后的行为保持锚点，不要随意改。
5. 如果改 objective、semantic weighting、terminal selection、solver 或 source ordering，必须说明旧结果和新结果可能不再直接可比。
6. `source_rerank` 默认关闭，只在显式消融中开启。

## 固定 baseline 范围

论文目标 baseline 集合继承旧仓库规划：

1. `NaiveGeneration`
2. `BM25`
3. `StandardRAG`
4. `HybridRAG`
5. `GraphRAG`
6. `LightRAG`
7. `PathRAG`
8. `HyperGraphRAG`
9. `SWHC`

不要静默增删 baseline。若新增或删除，必须更新 `TASK.md` 和实验说明。

## 固定数据集范围

目标数据集集合：

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

当前已迁移的数据集文件在：

`evaluation/datasets/`

## 代码结构规则

当前仓库结构含义：

- `swhc/legacy/`
  - 从旧仓库评测侧复制的 SWHC 核心实现。
  - 用作行为保持基线。

- `swhc/core/`
  - 新 SWHC 方法实现的目标位置。
  - 当前先以 thin facade 形式代理 legacy。
  - 后续逐步拆出 terminal selection、scoring、objective、solver、export。

- `swhc/adapters/`
  - 上游图存储和 SWHC core 之间的适配层。
  - HyperGraphRAG 相关适配放这里。

- `swhc/diagnostics/`
  - SWHC debug、证据覆盖、answer exposure、失败样本分析工具。

- `evaluation/hypergraphrag/`
  - 迁移来的完整评测侧 HyperGraphRAG 包。
  - 用于复现实验和 baseline 运行。

- `evaluation/methods/`
  - baseline 和 SWHC 的评测入口。

- `docs/upstream_hypergraphrag/`
  - 旧仓库文档、历史任务和实验记录归档。

- `paper/`
  - 论文大纲、方法章节、实验章节和图表素材。

## 实验与记录规则

任何实验或影响实验定义的改动，都要写入 `EXPERIMENT_LOG.md`。

记录至少包括：

1. 日期
2. 方法
3. 数据集
4. 阶段
5. 命令
6. 配置
   - 模型
   - embedding
   - 是否启用 LLM judge
   - SWHC 关键参数
7. 输出路径
8. 结果摘要
9. 是否影响历史结果可比性
10. 下一步

中间实验默认关闭 LLM judge：

```powershell
$env:HGRAG_ENABLE_LLM_JUDGE="false"
```

## 开发规则

- 优先使用 `rg` 搜索。
- 不要大规模重构已验证路径。
- 不要删除或覆盖用户已有改动。
- 不要迁移或提交 API key、原始大数据、索引产物、大日志。
- 代码改动后至少运行语法或导入检查。
- 若修改评测逻辑、数据划分、指标定义、检索逻辑，必须在回复和日志中明确说明。

## 当前首要方向

本仓库当前不是重新做 baseline plumbing，而是：

1. 完成迁移后 parity check。
2. 把 SWHC 从 legacy 拆成清晰模块。
3. 围绕论文主线优化方法：
   - hypergraph-aware distance
   - terminal selection
   - objective refinement
   - query-aware evidence compression
   - answer-candidate exposure

