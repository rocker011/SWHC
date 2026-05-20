# 当前缺口清单

最后更新：`2026-05-20`

## 已经具备

- SWHC 独立仓库骨架。
- SWHC legacy 行为保持实现。
- 当前可用 baseline：
  - `NaiveGeneration`
  - `BM25`
  - `StandardRAG`
  - `HybridRAG`
  - `GraphRAG`
  - `HyperGraphRAG`
  - `SWHC`
- 当前已迁移数据集：
  - `hypertension`
  - `agriculture`
  - `cs`
  - `legal`
  - `mix`
  - `hotpotqa`
  - `hotpotqa_64`
  - `hotpotqa_probe`
- `.env` / `.env.example` 已配置为 `deepseekv4flash`。
- 配置读取器已支持优先读取环境变量和 `.env`。

## 仍然缺少

### 1. 真实 API key

本地 `.env` 已支持配置真实 API key，且 `.env` 已被 `.gitignore` 忽略，不会提交到仓库。

新环境首次使用时仍需自行创建或填写：

```text
OPENAI_API_KEY=你的真实key
```

### 2. Parity check

新仓库还没有和旧仓库做 SWHC 输出一致性对齐。

优先做：

- `hotpotqa_probe`
- `hotpotqa_64`
- `hypertension` 小样本

### 3. 尚未迁移或尚未接入的目标 baseline

旧规划中的目标 baseline 里，目前还缺：

- `LightRAG`
- `PathRAG`

当前仓库已迁移的是原仓库已有实现，不代表论文最终 baseline 已补齐。

### 4. 尚未准备的目标公开数据集

旧规划中的目标公开数据集里，目前还缺：

- `2WikiMultiHopQA`
- `MuSiQue`
- `PopQA`

当前只有 `hotpotqa` 相关小规模/转换文件。

### 5. 旧实验结果 JSON

没有迁移旧 `evaluation/results/`。

这是有意跳过的，原因是：

- 避免把大结果和中间产物混进新仓库。
- 先保持新仓库清爽。
- 需要时再选择性归档结果摘要或复现实验。

### 6. 图索引 workspace

没有迁移：

- `evaluation/expr/`
- `evaluation/expr_official_graphrag/`

因此如果要直接跑 Step2，需要先确认对应数据集是否已经完成 Step1 索引，或重新构建索引。

### 7. 测试体系还不完整

当前只有轻量 diagnostics 测试。

下一步需要补：

- tiny hypergraph fixture
- objective 单元测试
- solver snapshot/parity 测试
- context export 测试

### 8. 依赖声明仍偏轻

`pyproject.toml` 当前只列了独立 SWHC 最小依赖。

完整评测可能还需要旧仓库依赖，例如：

- `openai`
- `tiktoken`
- `numpy`
- `networkx`
- `nano-vectordb`
- `simcse`
- official `graphrag` 相关包

当前建议继续使用已有 `hypergraphrag` conda 环境运行实验。

## 建议下一步

1. 运行最小配置检查。
2. 做 `hotpotqa_probe` 的 SWHC parity check。
3. 再开始拆分 `swhc/core/`。
