# 当前缺口清单

最后更新：`2026-05-20`

## 本次最小验证结论

- 单元测试已补充并通过：`5 tests OK`。
- `hotpotqa_probe` 已完成最小 Step1 索引构建。
- 以下方法已完成最小 Step2 生成：
  - `NaiveGeneration`
  - `BM25`
  - `StandardRAG`
  - `HybridRAG`
  - `HyperGraphRAG`
  - `SWHC`
- official `GraphRAG` 仍缺少 `evaluation/expr_official_graphrag/hotpotqa_probe/` workspace，因此当前不能直接运行。
- 本次没有运行 Step3 LLM judge，也没有跑完整数据集，以控制 API token 消耗。

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
- 当前已迁移上下文文件：
  - `agriculture_contexts.json`
  - `cs_contexts.json`
  - `hotpotqa_contexts.json`
  - `hotpotqa_64_contexts.json`
  - `hotpotqa_probe_contexts.json`
  - `hypertension_contexts.json`
  - `legal_contexts.json`
  - `mix_contexts.json`
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

新仓库已经完成 `hotpotqa_probe` 最小可运行检查，但还没有和旧仓库做 SWHC 输出一致性对齐。

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

当前本地已经为 `hotpotqa_probe` 重新生成 `evaluation/expr/hotpotqa_probe/`，但该目录仍作为运行产物被 `.gitignore` 忽略。

official `GraphRAG` 需要 `evaluation/expr_official_graphrag/<dataset>/`，目前仍缺少，需单独构建或迁移。

### 7. 测试体系还不完整

当前已有轻量 diagnostics、SWHC tiny graph、BM25 index 与本地配置读取测试。

下一步需要补：

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
