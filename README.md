# SWHC

`SWHC (Semantic Wiener HyperConnector)` 是一个面向 hypergraph-based RAG 的 query-time evidence assembly 方法。

本仓库是从以下旧项目迁移出来的独立研究仓库：

`D:\PythonProjects\HyperGraphRAG`

旧仓库只作为上游参考和归档来源；默认不要修改旧仓库。

## 当前状态

- 已建立独立项目骨架。
- 已迁移 SWHC 行为保持实现到 `swhc/legacy/`。
- 已建立 `swhc/core/`、`swhc/adapters/`、`swhc/diagnostics/`。
- 已迁移旧仓库文档、实验记录、baseline、评测脚本和当前可用数据集。
- 已整理中文项目治理文件：
  - `AGENTS.md`
  - `TASK.md`
  - `EXPERIMENT_LOG.md`
- 已新增架构说明：
  - `ARCHITECTURE.md`

## 主要目录

- `swhc/legacy/`
  - 从旧仓库评测侧复制的 SWHC 核心实现。
  - 作为行为保持和 parity check 基线。

- `swhc/core/`
  - 新 SWHC 方法实现的目标位置。
  - 当前先代理 legacy，后续逐步拆成真实模块。

- `swhc/adapters/`
  - 上游图存储与 SWHC core 的适配层。

- `swhc/diagnostics/`
  - 证据覆盖、answer exposure、失败样本等诊断工具。

- `evaluation/`
  - 迁移来的 baseline、评测脚本和数据集。

- `docs/upstream_hypergraphrag/`
  - 旧仓库文档、任务和实验记录归档。

- `UPSTREAM_EXPERIMENT_LOG.md`
  - 旧仓库完整实验记录的根目录副本，便于论文追溯。

- `paper/`
  - 论文大纲、方法章节和实验章节。

## 迁移原则

第一阶段目标是 **不改变行为的迁移**。

任何后续关于 objective、semantic distance、solver、terminal selection、source rerank 或 evidence compression 的改动，都必须记录到 `EXPERIMENT_LOG.md`，并说明是否影响旧结果可比性。

## 下一步

优先做 SWHC parity check：

1. 用新仓库跑小样本 SWHC Step2。
2. 与旧仓库相同参数下的 `test_knowledge.json` 对齐。
3. 确认迁移没有引入行为漂移。
4. 再开始拆分 `swhc/core/` 的真实实现。

## 本地实验配置

本仓库支持从 `.env` 读取本地实验配置。当前 `.env.example` 已按 `deepseekv4flash` 配好模板。

使用前需要把 `.env` 里的 `OPENAI_API_KEY` 替换为真实 key。

PowerShell 中也可以显式加载：

```powershell
. .\scripts\load_env.ps1
```

当前缺口清单见：

`docs/CURRENT_GAPS.md`
