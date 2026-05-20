# 迁移清单

源仓库：

`D:\PythonProjects\HyperGraphRAG`

目标仓库：

`D:\PythonProjects\SWHC`

## 已复制内容

### SWHC 行为保持实现

- `swhc/legacy/swhc.py`
- `swhc/legacy/base.py`
- `swhc/legacy/utils.py`
- `swhc/legacy/prompt.py`

### SWHC 新包结构

- `swhc/core/`
- `swhc/adapters/`
- `swhc/diagnostics/`

### baseline 与方法入口

- `evaluation/methods/`

当前包含：

- `naivegeneration.py`
- `bm25.py`
- `standardrag.py`
- `hybrid_rag.py`
- `graphrag.py`
- `graphrag_official_common.py`
- `hypergraphrag.py`
- `swhc.py`

### 评测运行代码

- `evaluation/hypergraphrag/`
- `evaluation/get_generation.py`
- `evaluation/get_score.py`
- `evaluation/inference_backend.py`
- `evaluation/script_*.py`
- `evaluation/see_score.py`
- `evaluation/prepare_hotpotqa.py`
- 相关评测说明文档

### 可用数据集

- `evaluation/datasets/agriculture`
- `evaluation/datasets/cs`
- `evaluation/datasets/hotpotqa`
- `evaluation/datasets/hotpotqa_64`
- `evaluation/datasets/hotpotqa_probe`
- `evaluation/datasets/hypertension`
- `evaluation/datasets/legal`
- `evaluation/datasets/mix`

### 上游文档和实验记录

- `docs/upstream_hypergraphrag/AGENTS.md`
- `docs/upstream_hypergraphrag/TASK.md`
- `docs/upstream_hypergraphrag/EXPERIMENT_LOG.md`
- `UPSTREAM_EXPERIMENT_LOG.md`
- `docs/upstream_hypergraphrag/project/`
- `docs/upstream_hypergraphrag/results/`
- `docs/upstream_hypergraphrag/figures/`
- `docs/upstream_hypergraphrag/baselines/`

### legacy quick-start 脚本

- `evaluation/scripts/construct_legacy.py`
- `evaluation/scripts/query_legacy.py`

## 有意跳过

- `api_config.txt`
- `evaluation/results/`
- `evaluation/expr/`
- `evaluation/expr_official_graphrag/`
- runtime logs
- provider keys
- 本地密钥或私有配置

## 已整理内容

- 删除根目录重复的 `UPSTREAM_*` 文件。
- 删除 `evaluation/methods/` 中重复的 `common_legacy.py` 和 `swhc_legacy_method.py`。
- 将根目录 legacy quick-start 脚本移动到 `evaluation/scripts/`。
- 将根目录治理文件改写为中文：
  - `AGENTS.md`
  - `TASK.md`
  - `EXPERIMENT_LOG.md`
- 新增：
  - `ARCHITECTURE.md`

## 兼容说明

迁移来的 baseline 和评测脚本目前仍保留旧项目运行约定，尤其是：

- 从 `evaluation/` 目录运行脚本。
- 通过 `evaluation/hypergraphrag/` 解析 `hypergraphrag` 包。

后续重构时，应先做 parity check，再逐步抽离依赖。
