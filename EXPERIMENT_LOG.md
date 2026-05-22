# EXPERIMENT_LOG.md

## 2026-05-23 - 文档结构收敛

- Goal:
  - 减少需要经常更新的文档数量，避免优化阶段计划分散在多个文件中。
- Changes:
  - 将优化阶段设定和当前缺口合并到 `TASK.md`。
  - 删除独立的 `docs/OPTIMIZATION_STAGE.md` 和 `docs/CURRENT_GAPS.md`。
  - `README.md` 只保留入口链接。
  - `AGENTS.md` 只保留长期规则和方法边界。
- Outcome:
  - 后续经常更新的文档只保留 `TASK.md` 与 `EXPERIMENT_LOG.md`。

## 2026-05-23 - SWHC 优化阶段实验设定冻结

- Goal:
  - 将仓库状态从迁移/parity 阶段切换到 SWHC 方法优化阶段。
  - 固定第一轮优化实验的数据集、方法集合、模型和 judge 设置。
- Code version:
  - 文档更新，不改实验代码。
- Command:
  - 未运行实验。
- Config:
  - 数据集：`hotpotqa_64`
  - 方法：
    - `HybridRAG`
    - `HyperGraphRAG`
    - `SWHC-legacy`
    - `SWHC-new`
  - 模型：`deepseek-v4-flash`
  - 模式：非 thinking
  - LLM judge：关闭，`HGRAG_ENABLE_LLM_JUDGE=false`
  - source rerank：默认关闭，`HGRAG_SWHC_SOURCE_RERANK=false`
- Output:
  - 更新 `TASK.md`
  - 更新 `README.md`
  - 更新 `AGENTS.md`
  - 更新 `.env.example`
- Result summary:
  - 后续优化实验以 `hotpotqa_64` 为第一轮主数据集。
  - `SWHC-legacy` 作为冻结基线，`SWHC-new` 作为优化版本。
  - V3.2 历史结果只作为参考，不与 V4-Flash 新结果混合作为论文主表。
- Comparability:
  - 本次只是实验设定更新，不产生新结果。
  - 后续任何 SWHC-new 改动都必须说明与 legacy 结果的可比性。
- Outcome:
  - 优化阶段实验边界已固定。
- Next action:
  - 新增 `SWHC-new` 独立入口和结果目录。
  - 在 `hotpotqa_probe` smoke test 后，运行 `hotpotqa_64` 四方法对比。

## 2026-05-22 - SWHC 迁移严格 parity check - hotpotqa_probe

- Goal:
  - 验证新仓库迁移版本在开始优化前，与旧仓库 SWHC 行为一致。
  - 允许使用 DeepSeek API，但尽量把严格比较从实时 LLM 波动中剥离出来。
- Code version:
  - 新仓库新增 `tools/parity_check.py`。
- Command:
  - `python tools/parity_check.py --old-root D:\PythonProjects\HyperGraphRAG --new-root D:\PythonProjects\SWHC --dataset hotpotqa_probe --run-e2e-cache-replay`
- Config:
  - 数据集：`hotpotqa_probe`
  - 严格比较使用旧仓库同一份 `evaluation/expr/hotpotqa_probe` 索引。
  - 固定查询：`Were Scott Derrickson and Ed Wood of the same nationality?`
  - 固定 low keywords：`SCOTT DERRICKSON, ED WOOD, AMERICAN`
  - 固定 high keywords：`<hyperedge>SCOTT DERRICKSON ED WOOD NATIONALITY`
  - live e2e 探针使用 `.env` 中的 `deepseek-v4-flash`。
- Output:
  - `reports/parity/hotpotqa_probe/parity_report.json`
  - `reports/parity/hotpotqa_probe/old_solver.json`
  - `reports/parity/hotpotqa_probe/new_solver.json`
  - `reports/parity/hotpotqa_probe/old_context.json`
  - `reports/parity/hotpotqa_probe/new_context.json`
- Result summary:
  - 核心迁移文件哈希一致：
    - `evaluation/hypergraphrag/base.py`
    - `evaluation/hypergraphrag/swhc.py`
    - `evaluation/hypergraphrag/operate.py`
    - `evaluation/methods/common.py`
    - `evaluation/methods/swhc.py`
  - tiny graph solver 输出完全一致。
  - 同一旧索引、同一固定关键词下的 SWHC context 完全一致。
  - live DeepSeek e2e 探针本次也输出一致，但不作为严格 parity gate。
- Comparability:
  - 本次确认新仓库迁移基线可信，可以开始在 `swhc/core/` 中做方法优化。
  - live e2e 不作为严格判据，因为当前 `only_need_context=True` 流程不会缓存最终 context，关键词抽取请求也没有单独缓存。
- Outcome:
  - 严格 parity check 通过。
- Next action:
  - 冻结当前 legacy 行为作为 baseline。
  - 后续优化前后用 `tools/parity_check.py` 保护迁移基线。

## 2026-05-20 - 迁移后最小冒烟测试 - hotpotqa_probe

- Goal:
  - 补充轻量测试文件。
  - 在尽量减少 API token 消耗的前提下，检查迁移后的 SWHC 与已迁移 baseline 是否能完成最小实验链路。
- Code version:
  - 本仓库 `main` 分支，初始提交之后的测试与上下文补充变更。
- Commands:
  - `python -m unittest discover -s tests -p "test_*.py" -v`
  - `python script_insert.py --cls hotpotqa_probe`
  - `python script_naivegeneration.py --data_source hotpotqa_probe`
  - `python script_bm25.py --data_source hotpotqa_probe --chunk_top_k 2 --token_budget 1000`
  - `python script_standardrag.py --data_source hotpotqa_probe --chunk_top_k 2 --token_budget 1000`
  - `python script_hybrid_rag.py --data_source hotpotqa_probe --bm25_top_k 2 --dense_top_k 2 --token_budget 1000 --rrf_k 10`
  - `python script_hypergraphrag.py --data_source hotpotqa_probe`
  - `python script_swhc.py --data_source hotpotqa_probe`
  - `python script_graphrag.py --data_source hotpotqa_probe`
- Config:
  - 数据集：`hotpotqa_probe`
  - 并发：`HGRAG_QUERY_CONCURRENCY=1`
  - BM25 / dense 检索 top-k 均使用小值。
  - token budget 使用 `1000`。
  - SWHC 关闭 source rerank：`HGRAG_SWHC_SOURCE_RERANK=false`。
  - LLM 后端使用本地 `.env` 中配置的 `deepseek-v4-flash`。
- Output:
  - 索引目录：`evaluation/expr/hotpotqa_probe/`
  - 最小生成结果：
    - `evaluation/results/NaiveGeneration/hotpotqa_probe/test_knowledge.json`
    - `evaluation/results/BM25/hotpotqa_probe/test_knowledge.json`
    - `evaluation/results/StandardRAG/hotpotqa_probe/test_knowledge.json`
    - `evaluation/results/HybridRAG/hotpotqa_probe/test_knowledge.json`
    - `evaluation/results/HyperGraphRAG/hotpotqa_probe/test_knowledge.json`
    - `evaluation/results/SWHC/hotpotqa_probe/test_knowledge.json`
- Result summary:
  - 单元测试通过：`5 tests OK`。
  - `hotpotqa_probe` Step1 索引生成成功。
  - `NaiveGeneration`、`BM25`、`StandardRAG`、`HybridRAG`、`HyperGraphRAG`、`SWHC` 均完成最小 Step2 生成。
  - official `GraphRAG` baseline 未运行成功，原因是缺少 `evaluation/expr_official_graphrag/hotpotqa_probe/` workspace。
- Comparability:
  - 本次只做迁移后的 smoke test，不作为论文结果。
  - 未运行 Step3 LLM judge，也未做完整数据集评测。
- Outcome:
  - 迁移后的 SWHC 与主要本地 baseline 最小链路可运行。
  - official GraphRAG 仍需先准备或迁移官方 workspace。
- Next action:
  - 补齐 official GraphRAG workspace 构建流程。
  - 选择 `hotpotqa_64` 或 `hypertension` 做下一轮低成本 parity check。

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

## 2026-05-20 - SWHC - deepseek-v4-flash 本地环境配置

- Goal:
  - 配置新仓库的本地 `.env`，默认使用 `deepseek-v4-flash` 做生成和 judge 模型。
  - 让评测配置支持从环境变量或 `.env` 读取，减少对 `api_config.txt` 的依赖。
- Changes:
  - 新增 `.env`
  - 新增 `.env.example`
  - 新增 `scripts/load_env.ps1`
  - 更新 `evaluation/hypergraphrag/openai_config.py`
  - 新增 `docs/CURRENT_GAPS.md`
- Config:
  - `OPENAI_BASE_URL=https://api.deepseek.com`
  - `OPENAI_MODEL=deepseek-v4-flash`
  - `HGRAG_GENERATION_MODEL=deepseek-v4-flash`
  - `HGRAG_JUDGE_MODEL=deepseek-v4-flash`
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
