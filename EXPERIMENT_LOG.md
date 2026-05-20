# EXPERIMENT_LOG.md

## 用途

这是 `SWHC` 独立仓库的追加式实验与迁移记录。

旧仓库完整实验记录已经归档在：

`docs/upstream_hypergraphrag/EXPERIMENT_LOG.md`

同时根目录保留了一份完整副本：

`UPSTREAM_EXPERIMENT_LOG.md`

本文件只记录新仓库中的迁移、重构、parity check、方法消融和论文实验。

## 记录规则

每条实验或重要工程变更至少记录：

1. 日期
2. 范围
3. 阶段
4. 命令
5. 配置
6. 输出
7. 结果摘要
8. 是否影响历史结果可比性
9. 下一步

对于 SWHC 实验，额外记录：

- `alpha`
- `beta`
- `gamma`
- `edge_weight_floor`
- `hop_cost`
- `candidate_hops`
- `budget_nodes`
- 是否启用 source rerank
- 是否改变 objective / solver / semantic weighting

如果 objective、solver、semantic edge weighting、terminal selection 或 context export 发生改变，必须明确写：

> 本次改动会影响 SWHC 结果与旧结果的直接可比性。

## 模板

```md
## YYYY-MM-DD - <scope> - <stage>

- Goal:
- Code version:
- Command:
- Config:
- Output:
- Result summary:
- Comparability:
- Outcome:
- Notes:
- Next action:
```

## 2026-05-20 - SWHC - 独立仓库骨架迁移

- Goal:
  - 新建 `D:\PythonProjects\SWHC`，作为 SWHC 独立研究仓库。
  - 不修改原始 `D:\PythonProjects\HyperGraphRAG` 仓库。
- Source:
  - `D:\PythonProjects\HyperGraphRAG`
- Output:
  - `D:\PythonProjects\SWHC`
- Result summary:
  - 建立目录：
    - `swhc/core/`
    - `swhc/legacy/`
    - `swhc/adapters/`
    - `swhc/diagnostics/`
    - `evaluation/`
    - `configs/`
    - `docs/`
    - `paper/`
    - `tests/`
  - 迁移 SWHC 行为保持实现到 `swhc/legacy/`。
  - 新增 `swhc/core/` thin facade。
- Comparability:
  - 不改变 SWHC 行为，不影响旧结果可比性。
- Outcome:
  - 成功。
- Next action:
  - 迁移旧项目文档、实验记录、baseline 和数据集。

## 2026-05-20 - SWHC - 上游文档、baseline 和数据集迁移

- Goal:
  - 将旧仓库中论文实验所需资产迁移到新仓库。
- Source:
  - `D:\PythonProjects\HyperGraphRAG`
- Output:
  - `docs/upstream_hypergraphrag/`
  - `evaluation/methods/`
  - `evaluation/hypergraphrag/`
  - `evaluation/datasets/`
  - `evaluation/script_*.py`
  - `evaluation/get_generation.py`
  - `evaluation/get_score.py`
- Skipped:
  - `api_config.txt`
  - `evaluation/results/`
  - 图索引 workspace
  - runtime logs
  - provider keys
- Result summary:
  - 已迁移 baseline：
    - `NaiveGeneration`
    - `BM25`
    - `StandardRAG`
    - `HybridRAG`
    - `GraphRAG`
    - `HyperGraphRAG`
    - `SWHC`
  - 已迁移数据集：
    - `hypertension`
    - `agriculture`
    - `cs`
    - `legal`
    - `mix`
    - `hotpotqa`
    - `hotpotqa_64`
    - `hotpotqa_probe`
- Checks:
  - 全量 Python 文件 `py_compile` 通过。
  - `import swhc` 通过。
  - 核心 baseline imports 通过。
  - `script_swhc.py --help` 通过。
- Comparability:
  - 仅迁移与兼容修复，不改变 SWHC 方法逻辑。
- Outcome:
  - 成功。
- Next action:
  - 做 SWHC parity check。

## 2026-05-20 - SWHC - 文件结构整理与中文项目治理文档

- Goal:
  - 将 `AGENTS.md`、`TASK.md`、`EXPERIMENT_LOG.md` 统一改写为中文。
  - 结合旧仓库规则，明确新仓库的 SWHC 研究边界、baseline 范围、数据集范围和实验记录规范。
  - 整理迁移后的文件架构。
- Changes:
  - 删除根目录重复的：
    - `UPSTREAM_AGENTS.md`
    - `UPSTREAM_TASK.md`
    - `UPSTREAM_EXPERIMENT_LOG.md`
  - 删除 `evaluation/methods/` 中重复的：
    - `common_legacy.py`
    - `swhc_legacy_method.py`
  - 将 quick-start legacy 脚本移动到：
    - `evaluation/scripts/construct_legacy.py`
    - `evaluation/scripts/query_legacy.py`
  - 新增中文架构说明：
    - `ARCHITECTURE.md`
- Comparability:
  - 文件组织变更，不改变 SWHC 方法逻辑。
- Outcome:
  - 成功。
- Next action:
  - 运行语法和导入检查。

## 2026-05-20 - SWHC - deepseekv4flash 本地环境配置

- Goal:
  - 配置新仓库的本地 `.env`，默认使用 `deepseekv4flash` 做生成和 judge 模型。
  - 让评测配置支持从环境变量或 `.env` 读取，减少对 `api_config.txt` 的依赖。
- Changes:
  - 新增 `.env`
  - 新增 `.env.example`
  - 新增 `scripts/load_env.ps1`
  - 更新 `evaluation/hypergraphrag/openai_config.py`
  - 新增 `docs/CURRENT_GAPS.md`
- Config:
  - `OPENAI_BASE_URL=https://api.deepseek.com`
  - `OPENAI_MODEL=deepseekv4flash`
  - `HGRAG_GENERATION_MODEL=deepseekv4flash`
  - `HGRAG_JUDGE_MODEL=deepseekv4flash`
  - `OPENAI_EMBED_MODEL=local:Qwen/Qwen3-Embedding-0.6B`
  - `HGRAG_ENABLE_LLM_JUDGE=false`
  - `HGRAG_SWHC_SOURCE_RERANK=false`
- Checks:
  - `load_openai_config()` 可读取 `.env`。
  - `openai_config.py` 语法检查通过。
  - 本地 `.env` 已确认被 `.gitignore` 忽略，不会进入 git 提交。
- Comparability:
  - 仅配置读取方式变更，不改变 SWHC 方法逻辑。
- Outcome:
  - 成功。
- Next action:
  - 做 API 连通性检查和 SWHC parity check。

## 2026-05-20 - SWHC - 旧实验日志完整根目录副本

- Goal:
  - 按用户要求，将原 `HyperGraphRAG/EXPERIMENT_LOG.md` 的完整实验记录复制到新仓库根目录，便于后续论文和实验追溯。
- Source:
  - `D:\PythonProjects\HyperGraphRAG\EXPERIMENT_LOG.md`
- Output:
  - `UPSTREAM_EXPERIMENT_LOG.md`
- Result summary:
  - 旧仓库实验日志完整复制，大小与原文件一致。
  - `docs/upstream_hypergraphrag/EXPERIMENT_LOG.md` 仍保留同一份归档。
- Comparability:
  - 文档迁移，不改变任何实验定义或 SWHC 方法逻辑。
- Outcome:
  - 成功。
- Next action:
  - 做提交前安全检查，确保 `.env` 和密钥不会进入 git。
