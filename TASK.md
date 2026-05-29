# TASK.md

最后更新：`2026-05-27`

## 当前阶段

当前进入 **SWHC 方法优化阶段**。

迁移、基础 smoke test 和 `hotpotqa_probe` 严格 parity check 已完成。后续优化以 `SWHC-legacy` 为冻结基线，在 `SWHC-new` 中做可追溯改动。

## 文档维护原则

- 经常更新的文档只保留两个：
  - `TASK.md`：当前阶段、实验设定、下一步任务和缺口。
  - `EXPERIMENT_LOG.md`：已经发生的实验、迁移、检查和重要工程变更。
- `README.md`、`AGENTS.md`、`ARCHITECTURE.md`、`MIGRATION_MANIFEST.md` 尽量保持稳定，不重复维护当前实验细节。
- `docs/upstream_hypergraphrag/` 和 `UPSTREAM_EXPERIMENT_LOG.md` 是归档材料，不作为当前任务看板。

## 已完成

1. 新建独立仓库：
   - `D:\PythonProjects\SWHC`

2. 迁移 SWHC 行为保持实现：
   - `swhc/legacy/swhc.py`
   - `swhc/legacy/base.py`
   - `swhc/legacy/utils.py`
   - `swhc/legacy/prompt.py`

3. 建立新方法包结构：
   - `swhc/core/`
   - `swhc/adapters/`
   - `swhc/diagnostics/`

4. 迁移 baseline 和评测代码：
   - `evaluation/methods/`
   - `evaluation/hypergraphrag/`
   - `evaluation/get_generation.py`
   - `evaluation/get_score.py`
   - `evaluation/inference_backend.py`
   - `evaluation/script_*.py`

5. 迁移已有数据集文件：
   - `hypertension`
   - `agriculture`
   - `cs`
   - `legal`
   - `mix`
   - `hotpotqa`
   - `hotpotqa_64`
   - `hotpotqa_probe`

6. 迁移旧仓库文档和实验记录：
   - `docs/upstream_hypergraphrag/`

7. 清理迁移残留：
   - 删除根目录重复的 `UPSTREAM_*` 文件
   - 删除 `evaluation/methods` 下重复的 `*_legacy` 文件
   - 将根目录 legacy quick-start 脚本收拢到 `evaluation/scripts/`

8. 已完成基础检查：
   - 全量 Python 文件 `py_compile` 通过
   - `import swhc` 通过
   - 核心 baseline imports 通过
   - `script_swhc.py --help` 通过

9. 已完成严格 parity check：
   - 核心迁移文件哈希一致
   - tiny graph solver 输出一致
   - 同一旧索引、同一固定关键词下的 context 输出一致
   - 报告：`reports/parity/hotpotqa_probe/parity_report.json`

10. 已实现 `SWHC-new v0` 工程入口：
    - 新增 `SWHC-legacy` 与 `SWHC-new` 独立方法入口。
    - `SWHC-new v0` 复用 legacy solver，只替换 context export。
    - v0 context 增加 `Relevant Evidence`，并保留 selected subgraph 的完整 `Entities / Relationships`。
    - `hotpotqa_probe` smoke test 已通过，且两类结果目录保持分离。

11. 已完成 `hotpotqa_64` shortest-answer-span 四方法对比：
    - `HybridRAG`：EM 0.6562，F1 0.8002，R-Sim 0.6028，平均 context tokens 11473.0。
    - `HyperGraphRAG`：EM 0.7188，F1 0.8402，R-Sim 0.6754，平均 context tokens 17236.9。
    - `SWHC-legacy`：EM 0.6875，F1 0.8420，R-Sim 0.6847，平均 context tokens 2743.5。
    - `SWHC-new`：EM 0.6875，F1 0.8344，R-Sim 0.7157，平均 context tokens 3572.8。

## P0：当前必须先做

1. **冻结 legacy baseline**
   - `swhc/legacy/` 不作为优化改动位置。
   - 当前 `evaluation/methods/swhc.py` 对应 `SWHC-legacy`。
   - 后续新增 `SWHC-new` 时，必须使用独立入口和独立结果目录，避免覆盖 legacy 结果。

2. **优化阶段固定实验设置**
   - 数据集：`hotpotqa_64`
   - 方法：
     - `HybridRAG`
     - `HyperGraphRAG`
     - `SWHC-legacy`
     - `SWHC-new`
   - 模型：`deepseek-v4-flash`
   - 模式：非 thinking
   - 输出：短答案 span，`HGRAG_SHORTEST_ANSWER_SPAN=true`
   - LLM judge：关闭，`HGRAG_ENABLE_LLM_JUDGE=false`
   - source rerank：默认关闭，`HGRAG_SWHC_SOURCE_RERANK=false`

3. **验证 SWHC-new 入口**
   - 目标：让优化版本和 legacy 版本可并行运行、可直接对比。
   - 输出建议：
     - `evaluation/results/SWHC-legacy/hotpotqa_64/`
     - `evaluation/results/SWHC-new/hotpotqa_64/`
   - 在结果目录和实验日志里显式记录 variant 名称。

4. **模块化拆分计划**
   - 当前 `swhc/core/*` 仍是 facade。
   - 下一步逐个从 `swhc/legacy/swhc.py` 拆出真实实现：
     - `terminal_selection.py`
     - `scoring.py`
     - `objective.py`
     - `solver.py`
     - `export.py`
   - 每拆一个模块，都要跑 tiny fixture 和 parity check。

5. **tiny hypergraph fixture**
   - 在 `tests/fixtures/` 建一个最小 hypergraph。
   - 覆盖：
     - terminal weight
     - semantic edge weight
     - objective
     - initial connector
     - bridge augmentation
     - pruning
     - context export

6. **论文方法草稿**
   - 在 `paper/method.md` 写出：
     - 问题定义
     - hypergraph representation
     - semantic terminal-aware Wiener objective
     - practical solver
     - context export

## P1：方法优化方向

1. **更 hypergraph-aware 的距离设计**
   - 区分 entity → hyperedge 与 hyperedge → entity 的代价。
   - 引入 hyperedge 覆盖多个 terminal 的奖励。
   - 重新讨论 `conf` 在跨方法比较中的解释。

2. **terminal selection 优化**
   - entity/hyperedge 平衡。
   - terminal diversity。
   - 避免多个 terminal 指向同一事实。
   - 增强多跳 bridge-oriented terminal。

3. **objective refinement**
   - 测试 token cost 替换为 entity/source 数量成本。
   - 解释或替换当前 `Tok(v) / 256`。
   - 增加 source coverage 或 evidence exposure 项作为显式消融。

4. **query-aware evidence compression**
   - 旧实验诊断显示：SWHC 经常找到了包含答案的 source，但答案没有被提升到结构化证据。
   - 可考虑新增：
     - `Relevant Evidence`
     - answer-candidate spans
   - 这必须作为新 variant，不要静默改变默认 SWHC。

## P2：论文实验扩展

1. 保留并复现旧结果：
   - `hypertension` 六方法 no-judge 表
   - `hotpotqa_64` normal prompt 表
   - `hotpotqa_64` shortest-answer-span 表

2. 扩展数据集：
   - 完整或更大规模 `HotpotQA`
   - `2WikiMultiHopQA`
   - `MuSiQue`
   - `PopQA`

3. 增加诊断指标：
   - Supporting Fact Recall / F1
   - F1 per Token
   - terminal count
   - selected node count
   - source count
   - answer-in-source rate
   - answer-in-entities/relationships rate

## 当前缺口

- `SWHC-new v0` 已实现，并已完成 `hotpotqa_probe` smoke test 与 `hotpotqa_64` 四方法短输出对比。
- `SWHC-new v0` 在本轮中 R-Sim 高于 legacy，但 EM 持平、F1 略低；下一步需要做失败样本和 answer exposure 诊断。
- official `GraphRAG` 仍缺少 `evaluation/expr_official_graphrag/<dataset>/` workspace。
- `LightRAG`、`PathRAG` 尚未接入；优化阶段暂不处理。
- 目标公开数据集 `2WikiMultiHopQA`、`MuSiQue`、`PopQA` 尚未准备；优化阶段先不扩展。
- 测试还缺 objective、solver snapshot/parity、context export 的细粒度覆盖。
- `pyproject.toml` 仍是最小依赖声明，完整评测继续优先使用已有 `hypergraphrag` conda 环境。

## 当前默认实验约束

- 中间实验默认关闭 LLM judge。
- 当前优化阶段固定使用 `deepseek-v4-flash` 非 thinking 模式。
- 当前优化阶段固定数据集为 `hotpotqa_64`。
- 当前优化阶段固定方法为 `HybridRAG`、`HyperGraphRAG`、`SWHC-legacy`、`SWHC-new`。
- 当前 `hotpotqa_64` 默认使用 shortest-answer-span 短输出：`HGRAG_SHORTEST_ANSWER_SPAN=true`。
- 不重跑已经完成的大型 pipeline，除非明确需要。
- 修改 SWHC objective、edge weighting、terminal selection、solver、source rerank 时，必须说明旧结果不可直接比较。
- `HGRAG_SWHC_SOURCE_RERANK` 默认保持 `false`。

## 参考归档

旧仓库对应文件已经迁移到：

- `docs/upstream_hypergraphrag/AGENTS.md`
- `docs/upstream_hypergraphrag/TASK.md`
- `docs/upstream_hypergraphrag/EXPERIMENT_LOG.md`

迁移清单见：

- `MIGRATION_MANIFEST.md`
