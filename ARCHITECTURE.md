# SWHC 仓库架构说明

## 总览

本仓库从 `D:\PythonProjects\HyperGraphRAG` 迁移而来，但目标不是复制一个新 HyperGraphRAG，而是把 SWHC 独立成一个可持续优化、可写论文、可复现实验的研究项目。

当前架构分成五层：

```text
SWHC/
├─ swhc/                 # SWHC 独立方法包
├─ evaluation/           # baseline、数据集、评测脚本
├─ docs/                 # 方法文档、旧仓库归档、结果分析
├─ experiments/          # 消融、表格、notebook
├─ paper/                # 论文草稿与图表资产
└─ tests/                # 单元测试、集成测试、fixtures
```

## `swhc/`

### `swhc/legacy/`

行为保持层。

这里保存从旧仓库评测侧迁移来的 SWHC 核心实现：

- `swhc.py`
- `base.py`
- `utils.py`
- `prompt.py`

规则：

- 迁移 parity check 完成前，不要随意修改。
- 后续新方法改动不要直接写在这里。
- 它是判断新实现是否偏离旧实现的基准。

### `swhc/core/`

新方法层。

当前先作为 thin facade 调用 `swhc/legacy/`，后续逐步拆成真实模块：

- `terminal_selection.py`
- `scoring.py`
- `objective.py`
- `solver.py`
- `export.py`
- `graph_types.py`

目标：

- 让 SWHC 方法本体脱离旧 HyperGraphRAG 文件结构。
- 让每个研究问题有明确落点。
- 支持 objective、distance、solver、evidence compression 的独立消融。

### `swhc/adapters/`

适配层。

用于把不同上游图索引系统接入 SWHC core。当前重点是 HyperGraphRAG：

- `storage_protocols.py` 定义 SWHC 需要的最小存储接口。
- `hypergraphrag_adapter.py` 后续承接 HyperGraphRAG 存储对象适配。

### `swhc/diagnostics/`

诊断层。

用于分析 SWHC 的：

- selected nodes
- terminal coverage
- source coverage
- answer-in-source
- answer-in-entities/relationships
- failure cases

## `evaluation/`

评测复现层。

从旧仓库迁移了：

- `evaluation/hypergraphrag/`
- `evaluation/methods/`
- `evaluation/datasets/`
- `evaluation/get_generation.py`
- `evaluation/get_score.py`
- `evaluation/inference_backend.py`
- `evaluation/script_*.py`

### `evaluation/methods/`

包含当前 baseline 和目标方法入口：

- `naivegeneration.py`
- `bm25.py`
- `standardrag.py`
- `hybrid_rag.py`
- `graphrag.py`
- `hypergraphrag.py`
- `swhc.py`

### `evaluation/hypergraphrag/`

完整迁移的评测侧 HyperGraphRAG 包。

用途：

- 复现旧实验。
- 支撑当前 baseline。
- 在 SWHC 完全抽离前提供上游图索引和存储实现。

### `evaluation/datasets/`

当前已迁移：

- `hypertension`
- `agriculture`
- `cs`
- `legal`
- `mix`
- `hotpotqa`
- `hotpotqa_64`
- `hotpotqa_probe`

注意：

- 这些是当前可用的问题文件和小规模数据资产。
- 更大数据集或原始数据下载流程后续再补。

### `evaluation/scripts/`

放置 legacy quick-start 脚本：

- `construct_legacy.py`
- `query_legacy.py`

## `docs/`

文档层。

- `docs/method/`
  - SWHC 方法说明。

- `docs/upstream_hypergraphrag/`
  - 旧仓库文档、任务和实验记录归档。

- `docs/results/`
  - 新仓库后续结果分析。

- `docs/figures/`
  - 新仓库后续图表。

## `paper/`

论文层。

当前已有：

- `outline.md`

后续建议新增：

- `method.md`
- `experiments.md`
- `related_work.md`
- `limitations.md`

## `tests/`

测试层。

当前已有轻量 diagnostics 测试。

下一步应补：

- tiny hypergraph fixture
- objective unit test
- solver parity test
- context export snapshot test

## 后续整理原则

1. 先做 parity check，再改方法。
2. 新方法改动进入 `swhc/core/`，不要直接改 `swhc/legacy/`。
3. baseline 复现留在 `evaluation/`。
4. 论文材料留在 `paper/` 和 `docs/results/`。
5. 每次影响实验定义的改动都写入 `EXPERIMENT_LOG.md`。

