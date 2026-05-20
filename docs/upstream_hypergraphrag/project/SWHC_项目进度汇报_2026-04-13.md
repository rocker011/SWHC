# HyperGraphRAG 复现进度汇报

更新时间: 2026-04-13

## 1. 当前结论

截至目前，`HyperGraphRAG` 已在 `hypertension` 数据集上完成从建图到评分的完整复现，`Step1 ~ Step5` 全部跑通，能够产出论文评测流程所需的中间结果和最终分数。

当前复现进度可以概括为：

- 已完成：代码阅读与流程梳理
- 已完成：评测数据下载与目录整理
- 已完成：当前环境适配（本地 embedding + 远程 LLM）
- 已完成：`hypertension` 单域完整实验
- 未完成：其余 4 个领域数据集复现
- 未完成：`StandardRAG / NaiveGeneration` baseline 对照实验

## 2. 已完成工作

### 2.1 代码与流程梳理

已完成对仓库核心代码的阅读，已明确论文评测实际使用的是 `evaluation/hypergraphrag/` 这套实现，而不是根目录下的 demo 代码。

已整理完整代码讲解文档：

- `D:\PythonProjects\HyperGraphRAG\HYPERGRAPHRAG_CODE_WALKTHROUGH.md`

### 2.2 数据准备

已根据 `evaluation/README.md` 下载并整理评测数据，目录结构已就位：

- `evaluation/contexts/*.json`
- `evaluation/datasets/*/questions.json`

其中 `hypertension` 数据集统计如下：

- 原始文档数：`107`
- 评测问题数：`512`
- binary 问题：`256`
- n-ary 问题：`256`
- 1-hop / 2-hop / 3-hop：`256 / 128 / 128`

### 2.3 环境适配与代码修复

由于当前 API 无法调用远程 embedding 接口，已将仓库改为：

- 本地 embedding：`Qwen/Qwen3-Embedding-0.6B`
- 远程 LLM：OpenAI-compatible chat 接口

同时为保证评测可跑通，完成了几项最小必要修复：

1. 增加本地 embedding 配置解析与加载逻辑  
2. 修复 Windows 控制台编码问题  
3. 修复异步限流器在异常时不释放计数的问题  
4. 对 Step1 的 entity summary 阶段单独限流，避免 `429 rate limit`  
5. 为 Step2 / Step3 / Step4 增加并发可控参数，保证长流程稳定运行

## 3. `hypertension` 复现结果

### 3.1 Step1: Knowledge HyperGraph Construction

已完成建图，输出目录：

- `D:\PythonProjects\HyperGraphRAG\evaluation\expr\hypertension`

建图后索引规模：

- Documents indexed: `107`
- Chunks indexed: `225`
- Entity vectors: `10851`
- Hyperedge vectors: `5067`
- Graph nodes: `15918`
- Graph edges: `19951`

说明：

- 图中节点由 `entity nodes + hyperedge nodes` 组成
- 当前实现用二部图来表达超图

### 3.2 Step2: Retrieve Knowledge

已完成检索，输出文件：

- `D:\PythonProjects\HyperGraphRAG\evaluation\results\HyperGraphRAG\hypertension\test_knowledge.json`

结果说明：

- 共 `512` 条问题样本
- 每条样本均已生成 `knowledge`
- `knowledge` 中包含三部分：
  - `Entities`
  - `Relationships`
  - `Sources`

### 3.3 Step3: Generate Based on Retrieved Knowledge

已完成生成，输出文件：

- `D:\PythonProjects\HyperGraphRAG\evaluation\results\HyperGraphRAG\hypertension\test_generation.json`

结果说明：

- 共 `512` 条样本
- 无生成报错
- 大部分样本按要求输出 `<answer>...</answer>`

### 3.4 Step4: Evaluate the Generation

已完成评分，输出文件：

- `D:\PythonProjects\HyperGraphRAG\evaluation\results\HyperGraphRAG\hypertension\test_result.json`
- `D:\PythonProjects\HyperGraphRAG\evaluation\results\HyperGraphRAG\hypertension\test_score.json`

总体得分：

- `EM = 21.29`
- `F1 = 34.40`
- `R-Sim = 66.53`
- `Gen = 55.63`

分组结果：

| Split | F1 | R-Sim | Gen |
|---|---:|---:|---:|
| Binary | 34.60 | 66.22 | 56.09 |
| N-ary | 34.20 | 66.84 | 55.17 |
| Overall | 34.40 | 66.53 | 55.63 |

### 3.5 结果初步解读

目前最明显的现象是：

- `R-Sim` 明显高于 `EM/F1`

这说明当前系统在“检索到相关知识”这件事上已经能工作，但检索优势尚未充分转化为最终答案质量。换句话说：

- 检索链路基本跑通
- 生成链路和答案对齐仍是当前性能瓶颈

## 4. 当前主要问题与已解决问题

### 已解决问题

1. 远程 embedding 接口不可用  
   已改为本地 `Qwen3-Embedding-0.6B`

2. Step1 中 entity summary 阶段频繁触发 `429 rate limit`  
   已通过单独限流和更强 retry/backoff 解决

3. Windows 控制台编码导致流程中断  
   已修复

### 仍需注意的问题

1. Step4 评分非常慢  
   原因是 `Gen` 指标需要大量 LLM judge 调用。以 `hypertension` 为例，`512` 条样本、`7` 个维度，总 judge 请求量约为 `3584` 次。

2. 当前 baseline 尚未全部补齐  
   目前只完整跑通了 `HyperGraphRAG / hypertension`，尚未补做：
   - `StandardRAG`
   - `NaiveGeneration`

3. 当前 repo 中的 `StandardRAG` 实现并非独立 dense retrieval  
   它是从 HyperGraphRAG 的 `Sources` 部分截取得到，因此严格意义上不是完全独立实现的标准基线。后续做正式对照时需要说明这一点。

## 5. 当前阶段性判断

当前可以认为：

1. 论文复现的主流程已经打通  
   至少在 `hypertension` 上，Step1~Step5 已全部成功执行

2. 当前环境已经具备继续扩展到其他数据集的能力  
   `agriculture / cs / legal / mix` 可以沿用同一套配置继续跑

3. 当前最值得优先推进的，不是再改建图代码，而是补齐对照实验与多域结果  
   这样才能形成更完整的 baseline 结论

## 6. 下一步计划

建议后续按以下顺序推进：

1. 跑完 `hypertension` 上的 baseline 对照  
   - `StandardRAG`
   - `NaiveGeneration`

2. 将当前稳定配置推广到其余四个数据集  
   - `agriculture`
   - `cs`
   - `legal`
   - `mix`

3. 汇总形成完整对照表  
   - 不同方法
   - 不同领域
   - binary / n-ary 分组结果

4. 如时间允许，再做小规模 ablation  
   优先考虑：
   - `top_k`
   - `chunk size`
   - entity extraction prompt
   - token budget

## 7. 当前可直接展示的材料

目前已经有可直接用于汇报或组会展示的材料：

1. 代码讲解文档  
   - `D:\PythonProjects\HyperGraphRAG\HYPERGRAPHRAG_CODE_WALKTHROUGH.md`

2. `hypertension` 结果摘要  
   - `D:\PythonProjects\HyperGraphRAG\evaluation\results\HyperGraphRAG\hypertension\hypertension_summary.md`

3. `hypertension` 指标图  
   - `D:\PythonProjects\HyperGraphRAG\evaluation\results\HyperGraphRAG\hypertension\hypertension_metrics.png`

## 8. 一句话汇报版

截至 2026 年 4 月 13 日，HyperGraphRAG 已在 `hypertension` 数据集上完成完整复现，建图、检索、生成、评分流程全部跑通，当前总体结果为 `EM 21.29 / F1 34.40 / R-Sim 66.53 / Gen 55.63`；下一步重点是补齐 baseline 对照和其余四个领域数据集。

