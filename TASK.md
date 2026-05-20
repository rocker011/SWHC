# TASK.md

最后更新：`2026-05-20`

## 当前阶段

当前处于 **迁移整理 + 行为一致性校验 + SWHC 模块化重构准备** 阶段。

目标不是立刻改方法，而是先把旧仓库中已经完成的 SWHC、baseline、数据集和实验记录整理成一个独立研究仓库，并保证迁移后的实现可以复现旧行为。

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

## P0：当前必须先做

1. **SWHC parity check**
   - 目标：确认新仓库迁移版 SWHC 与旧仓库同参数输出一致。
   - 优先数据集：
     - `hotpotqa_probe`
     - `hotpotqa_64`
     - `hypertension` 小样本
   - 输出：
     - 对比 `test_knowledge.json`
     - 记录差异来源
     - 若完全一致，标记 legacy parity baseline 成立

2. **配置整理**
   - 新仓库不迁移 `api_config.txt`。
   - 需要写明本地如何放置私有 API 配置。
   - 避免把 key、base url、供应商配置提交到仓库。

3. **模块化拆分计划**
   - 当前 `swhc/core/*` 仍是 facade。
   - 下一步逐个从 `swhc/legacy/swhc.py` 拆出真实实现：
     - `terminal_selection.py`
     - `scoring.py`
     - `objective.py`
     - `solver.py`
     - `export.py`
   - 每拆一个模块，都要跑 tiny fixture 和 parity check。

4. **tiny hypergraph fixture**
   - 在 `tests/fixtures/` 建一个最小 hypergraph。
   - 覆盖：
     - terminal weight
     - semantic edge weight
     - objective
     - initial connector
     - bridge augmentation
     - pruning
     - context export

5. **论文方法草稿**
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

## 当前默认实验约束

- 中间实验默认关闭 LLM judge。
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

