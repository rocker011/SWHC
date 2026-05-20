Skill 使用：未使用；当前可用 skill 仅用于“创建/安装 skill”，与本次“论文复现+代码导读”不匹配。

## A. 论文核心思想（工程复现向，11 句）

### 1) 为什么用超图而不是普通二元图（3 句）
1. HyperGraphRAG 的核心动机是很多事实天然是 n-ary（一个事实同时涉及多个实体和同一语义片段），若强行拆成二元边会丢失“同一事件/命题”的整体语义。  
2. 论文把“知识片段”建成 hyperedge，再把相关实体作为该 hyperedge 的连接点，这样语义最小单元是“片段级事实”而不是“实体对”。  
3. 这能避免 binary KG 常见的关系碎片化，让检索时直接命中完整事实块，减少后续生成时的拼接误差。  

### 2) 三步 pipeline 在做什么（3 句）
1. 构建阶段：对文本 chunk 做 LLM 抽取，得到 hyper-relations 与 entities，并落地为二部超图 + 向量索引（实体索引、超边索引、chunk 索引）。  
2. 检索阶段：query 先抽关键词/候选语义，再分别在实体与超边向量空间召回，并在图上做邻域扩展，拼成知识超图上下文 KH，同时配套来源文本上下文。  
3. 生成阶段：把结构化 KH 与文本上下文拼成最终上下文 K*，送入回答 prompt 生成答案。  

### 3) 相对 chunk-RAG / binary GraphRAG 的优势（5 句）
1. 对 chunk-RAG 来说，HyperGraphRAG 不是只做“向量相似 chunk 命中”，而是先命中结构化语义单元，再带回相关实体与证据源，降低“只命中字面相似段落”的噪声。  
2. 对 binary GraphRAG 来说，它避免把一个 n-ary 命题拆成多条 pairwise 边导致的语义断裂，这一点正是论文强调的 n-ary 拆分损失问题。  
3. 在检索后组装上，它不是简单拼 top-k 文本，而是做“实体->超边”和“超边->实体”的双向扩展，再融合来源 chunk，组装出的上下文更像一组可解释的知识子图。  
4. 论文实验显示在 n-ary 比例更高的数据集上优势更明显，说明结构建模收益与事实复杂度正相关。  
5. 工程上你可以把它理解成“图结构约束下的上下文编排器”：先找语义单元，再找邻接证据，而不是从一开始就把所有信息压平在 chunk 相似度里。  

## B. 仓库导读（从入口到细节）

### P0：必须读
1. 入口类与主流程（构建+查询）：[hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:109)。看 `HyperGraphRAG.__post_init__`、`insert/ainsert`、`query/aquery`；正确信号是你能画出“docs->chunks->extract->graph/vdb->kg_query”的调用链。  
2. 核心算法实现（chunking/抽取/检索/上下文组装/生成）：[operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:35)。看 `chunking_by_token_size`、`extract_entities`、`kg_query`、`_build_query_context`、`_get_node_data`、`_get_edge_data`；正确信号是能说清每个函数输入输出字段。  
3. 提示词与输出格式协议： [prompt.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/prompt.py:13)。看 `entity_extraction`、`entiti_continue_extraction`、`rag_response`；正确信号是知道抽取输出记录分隔符和 tuple 字段顺序。  
4. 默认存储落地（JSON KV + NanoVectorDB + NetworkX）：[storage.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/storage.py:26)。正确信号是知道最终会落什么文件、哪些字段进图、哪些字段进向量库。  
5. 快速可运行入口： [script_construct.py](/D:/PythonProjects/HyperGraphRAG/script_construct.py:1) 和 [script_query.py](/D:/PythonProjects/HyperGraphRAG/script_query.py:1)。正确信号是同一 `working_dir` 下先 construct 后 query 能得到非空响应。  

### P1：建议读
1. 抽象接口（替换后端必须读）：[base.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/base.py:17)。看 `BaseVectorStorage/BaseGraphStorage/BaseKVStorage` 的契约方法。  
2. 可替换后端实现： [neo4j_impl.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/kg/neo4j_impl.py:25)、[milvus_impl.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/kg/milvus_impl.py:12)、[chroma_impl.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/kg/chroma_impl.py:11)、[mongo_impl.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/kg/mongo_impl.py:11)。  
3. 上下文融合与截断逻辑： [utils.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/utils.py:296)。看 `process_combine_contexts`、`truncate_list_by_token_size`。  
4. 评测脚本主链： [evaluation/README.md](/D:/PythonProjects/HyperGraphRAG/evaluation/README.md:35)、[script_insert.py](/D:/PythonProjects/HyperGraphRAG/evaluation/script_insert.py:9)、[script_hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/evaluation/script_hypergraphrag.py:17)、[get_generation.py](/D:/PythonProjects/HyperGraphRAG/evaluation/get_generation.py:17)、[get_score.py](/D:/PythonProjects/HyperGraphRAG/evaluation/get_score.py:19)。  

### P2：需要时再读
1. 多 LLM/Embedding 适配： [llm.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/llm.py:503)。  
2. 数据库扩展实现细节（Oracle/TiDB）：`hypergraphrag/kg/oracle_impl.py`、`hypergraphrag/kg/tidb_impl.py`。  
3. 评分细节： [eval.py](/D:/PythonProjects/HyperGraphRAG/evaluation/eval.py:1)、[eval_r.py](/D:/PythonProjects/HyperGraphRAG/evaluation/eval_r.py:1)、[eval_g.py](/D:/PythonProjects/HyperGraphRAG/evaluation/eval_g.py:1)、[see_score.py](/D:/PythonProjects/HyperGraphRAG/evaluation/see_score.py:33)。  

### 关键点 1-8 对照（文件/函数一一对应）
1. 入口类与参数/insert/query：`HyperGraphRAG` 在 [hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:109)，`insert/ainsert` 在 :270/:274，`query/aquery` 在 :493/:497，查询核心在 [operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:484) 的 `kg_query`。  
2. chunking：`chunk_token_size/chunk_overlap_token_size` 定义在 [hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:129)，实际切分在 [operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:35)。  
3. n-ary 抽取与输出结构：prompt 在 [prompt.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/prompt.py:13)；抽取函数 `extract_entities` 在 [operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:261)；单条记录解析在 :87、:115；entity 结构含 `entity_name/entity_type/description/weight/hyper_relation/source_id`，hyperedge 结构含 `hyper_relation/weight/source_id`。  
4. 超图存储（二部图）：`_merge_hyperedges_then_upsert` 把超边作为 `role="hyperedge"` 节点（[operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:134)），`_merge_nodes_then_upsert` 把实体作为 `role="entity"` 节点（:167），`_merge_edges_then_upsert` 建立超边->实体连接（:215）；图后端默认 [NetworkXStorage](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/storage.py:178)。  
5. 三个向量库用途：初始化在 [hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:224)（`entities_vdb`）、:230（`hyperedges_vdb`）、:236（`chunks_vdb`）；检索 top-k 在 `entities_vdb.query`([operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:743)) 和 `hyperedges_vdb.query`(:938)；阈值默认 `cosine_better_than_threshold=0.2` 在 [storage.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/storage.py:68)。  
6. 检索后扩展（实体<->超边）：实体路径扩展在 `_find_most_related_edges_from_entities`([operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:881))、`_find_most_related_text_unit_from_entities`(:807)；超边路径扩展在 `_find_most_related_entities_from_relationships`(:1018)、`_find_related_text_unit_from_relationships`(:1058)；融合在 `combine_contexts`(:1108)。  
7. 生成与 K* 组装：上下文模板组装在 `_build_query_context`([operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:638))，回答 prompt 在 `PROMPTS["rag_response"]`([prompt.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/prompt.py:190))，LLM 调用在 `kg_query` 的 `use_model_func(...)`([operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:606))。  
8. 可替换组件与最小改动：抽象接口在 [base.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/base.py:50)，实现选择在 `_get_storage_class`([hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:250))；最小替换是构造时改 `vector_storage/graph_storage/kv_storage`，若新增后端则实现 Base* 接口并注册到 `_get_storage_class`。  

## C. “最快复现”操作手册

### 路径 1：最小跑通（example_contexts.json 建图 + query）
1. 进入仓库根目录：`cd D:\PythonProjects\HyperGraphRAG`。  
2. 建环境：`conda create -n hypergraphrag python=3.11 -y`。  
3. 激活并装依赖：`conda activate hypergraphrag`，`pip install -r requirements.txt`。  
4. 配置根目录 `api_config.txt`（四行依次为 key / base_url / chat_model / embed_model）。  
5. 先构图：`python script_construct.py`。  
6. 再查询：`python script_query.py`。  
7. 校验产物目录：`expr/example/` 下应出现 `graph_chunk_entity_relation.graphml`、`kv_store_full_docs.json`、`kv_store_text_chunks.json`、`vdb_entities.json`、`vdb_hyperedges.json`、`vdb_chunks.json`。  
8. 校验日志：根目录应有 `hypergraphrag.log`，并能看到 chunking/extraction/query 相关日志。  
9. 常见坑 1：`script_construct.py` 和 `script_query.py` 的 `working_dir` 必须一致（都用 `expr/example`），否则查询不到已建图。  
10. 常见坑 2：API key 无效/限流会导致抽取为空；可降低并发（构造参数 `llm_model_max_async`、`embedding_func_max_async`）再试。  

### 路径 2：论文式评测（evaluation Step1~Step5）
1. 进入评测目录：`cd D:\PythonProjects\HyperGraphRAG\evaluation`。  
2. 写 `api_config.txt`：依次填写 key、base_url、chat_model、embed_model。  
3. 准备数据目录：`contexts/{cls}_contexts.json` 与 `datasets/{cls}/questions.json`，结构按 [evaluation/README.md](/D:/PythonProjects/HyperGraphRAG/evaluation/README.md:12)。  
4. Step1 建图：`python script_insert.py --cls hypertension`。  
5. Step1 正确性检查：`expr/hypertension/` 下出现 graph/kv/vdb 文件，且无持续重试失败日志（见 [script_insert.py](/D:/PythonProjects/HyperGraphRAG/evaluation/script_insert.py:13)）。  
6. Step2 检索：`python script_hypergraphrag.py --data_source hypertension`。  
7. Step2 正确性检查：`results/HyperGraphRAG/hypertension/test_knowledge.json` 生成，且每条样本含 `knowledge` 字段（见 [script_hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/evaluation/script_hypergraphrag.py:30)）。  
8. 为对照法生成检索文件：`python script_standardrag.py --data_source hypertension` 与 `python script_naivegeneration.py --data_source hypertension`。  
9. Step3 生成：`python get_generation.py --data_sources hypertension --methods HyperGraphRAG,StandardRAG,NaiveGeneration`。  
10. Step3 正确性检查：每个方法目录下有 `test_generation.json`，且每条样本含 `generation`（见 [get_generation.py](/D:/PythonProjects/HyperGraphRAG/evaluation/get_generation.py:69)）。  
11. Step4 打分：分别执行 `python get_score.py --data_source hypertension --method HyperGraphRAG`（另两法同理）。  
12. Step5 看结果：`python see_score.py --data_source hypertension --method HyperGraphRAG`，并检查 `test_score.json` 与 `test_result.json`。  

必须一致的关键参数（公平比较）：
1. 生成模型：`gpt-4o-mini` 固定在 [get_generation.py](/D:/PythonProjects/HyperGraphRAG/evaluation/get_generation.py:48)。  
2. 检索 top-k：`QueryParam.top_k=60` 默认在 [base.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/base.py:24)，`script_hypergraphrag.py` 未改写。  
3. 相似度阈值：默认 0.2 在 [storage.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/storage.py:68)。  
4. seed：脚本未显式设置；若要可复现，建议统一 `temperature=0` 并固定 Python/NumPy 随机种子（当前代码未做）。  

## D. baseline 对照建议（更可信）

| 对照项 | 统一设置 | 说明 |
|---|---|---|
| 1. 生成模型 | 三方法都用同一 LLM（如 `gpt-4o-mini`） | 避免模型能力差异掩盖检索差异 |
| 2. Embedding 模型 | 三方法同一 embedding（如 `text-embedding-3-small`） | 保证召回空间一致 |
| 3. 检索预算 | 固定总上下文 token 上限 | 不让某方法靠更长上下文“作弊” |
| 4. top-k 策略 | 对齐 `k_V/k_H/k_C` 或至少对齐总召回数 | HyperGraphRAG 若仅用单 `top_k`，需在报告中说明 |
| 5. 评测输入 | 同一问题集、同一 golden answers、同一后处理 | EM/F1/Gen/R-Sim 才可横向比较 |
| 6. 运行设置 | 并发、重试、超时配置一致 | 降低 API 抖动导致的方差 |
| 7. 重复实验 | 每法至少 3 次报告均值/方差 | LLM 非确定性下更稳健 |
| 8. StandardRAG 定义 | 用独立 chunk retrieval 实现，不复用 HyperGraphRAG 输出切片 | 当前 [script_standardrag.py](/D:/PythonProjects/HyperGraphRAG/evaluation/script_standardrag.py:13) 是从 HyperGraphRAG 结果截 `Sources`，不够“标准 baseline” |

建议优先 ablation（敏感度从高到低）：
1. `top_k`（当前实体/超边共用）与 token budget（`max_token_for_*`）。  
2. `chunk_token_size` 与 `chunk_overlap_token_size`。  
3. 抽取 prompt（[prompt.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/prompt.py:13)）与 `entity_extract_max_gleaning`。  
4. 相似度阈值（默认 0.2）。  
5. 是否启用 local/global/hybrid 组合与融合策略（`combine_contexts`）。  

sanity check（快速验真）：
1. 随机抽样 30 条 query，人工检查 `knowledge` 中 hyperedge 文本是否直接支持答案主张。  
2. 对每条样本追溯 `source_id` 到 chunk 内容，检查是否出现“图里有关系但源文本无证据”。  
3. 分层统计 `nary==2` 与 `nary>2` 的检索命中质量，验证 HyperGraphRAG 对高 n-ary 子集是否更优。  
4. 对失败样本记录“关键词抽取失败 / 图扩展失败 / 生成偏航”三类错误占比。  

不确定但建议你优先确认的实现点：
1. 论文写有 `k_C` 的 chunk 检索项，但当前查询主链看起来主要依赖图节点 `source_id` 回捞 chunk，`chunks_vdb` 在查询阶段基本未被调用；请从 [hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:497) -> [operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:484) -> [operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:807) 复核。  
2. `aquery` 里显式分支仅 `mode in ["hybrid"]`，`local/global` 可能未完整接线；看 [hypergraphrag.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/hypergraphrag.py:497)。  
3. local 路径关系表可能把实体名当成 hyperedge 展示（`description = k[1]`）；看 [operate.py](/D:/PythonProjects/HyperGraphRAG/hypergraphrag/operate.py:906)。  

来源：
- 论文（arXiv）：https://arxiv.org/abs/2503.21322  
- 论文 HTML（方法与实验段落）：https://arxiv.org/html/2503.21322v2
