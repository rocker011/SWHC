# hotpotqa_probe 严格 parity check

本目录记录新仓库 `D:\PythonProjects\SWHC` 与旧仓库 `D:\PythonProjects\HyperGraphRAG`
在 `hotpotqa_probe` 上的迁移一致性检查。

## 结论

- 总结论：通过。
- 核心文件哈希：一致。
- tiny graph solver 输出：一致。
- 同一旧索引、同一固定关键词下的 SWHC context：一致。
- live DeepSeek end-to-end 探针：本次输出一致，但不作为严格 parity gate。

## 为什么 live e2e 不作为严格 gate

`script_swhc.py` 使用 `only_need_context=True`。当前 legacy 流程会在返回 context 前直接结束，
不会把最终 context 写入 `llm_response_cache`；关键词抽取请求本身也没有单独缓存。

因此 live e2e 会受到实时 LLM 输出波动影响。严格 parity 采用固定关键词与同一份旧索引，
直接比较 SWHC solver 和 context builder 的输出。

## 关键文件

- `parity_report.json`：完整机器可读报告。
- `old_solver.json` / `new_solver.json`：tiny graph solver 输出。
- `old_context.json` / `new_context.json`：固定关键词、同索引 context 输出。
- `old_e2e_test_knowledge.json` / `new_e2e_test_knowledge.json`：live DeepSeek 探针输出。

## 复现命令

```powershell
& 'C:\Users\dell\miniforge3\envs\hypergraphrag\python.exe' tools\parity_check.py `
  --old-root D:\PythonProjects\HyperGraphRAG `
  --new-root D:\PythonProjects\SWHC `
  --dataset hotpotqa_probe `
  --python 'C:\Users\dell\miniforge3\envs\hypergraphrag\python.exe' `
  --run-e2e-cache-replay
```
