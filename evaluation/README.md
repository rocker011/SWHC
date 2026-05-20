# HyperGraphRAG Evaluation

### Preparation
First, to evaluate HyperGraphRAG, we should use ```evaluation``` as the working directory. 
```bash
cd evaluation
```
Then, we need to set the root-level ```api_config.txt``` file. (We use [www.apiyi.com](https://www.apiyi.com/) for LLM server.)

```text
your_openai_api_key
https://your-openai-compatible-endpoint/v1
gpt-4o-mini
text-embedding-3-small
```

Last, we need download the contexts and datasets from [Terabox](https://1024terabox.com/s/13cV8oy4kXurqTzYl9j94-g) and put them in the ```contexts``` and ```datasets``` folders. 

```
HyperGraphRAG/
└── evaluation/
    ├── contexts/   
        ├── hypertension_contexts.json   
        ├── agriculture_contexts.json    
        ├── cs_contexts.json                  
        ├── legal_contexts.json                    
        └── mix_contexts.json    
    ├── datasets/           
        ├── hypertension/                             
            └── questions.json     
        ├── agriculture/                            
            └── questions.json 
        ├── cs/                            
            └── questions.json 
        ├── legal/                             
            └── questions.json 
        └── mix/                              
            └── questions.json
    └── api_config.txt                               
```

### Step1. Knowledge HyperGraph Construction
```bash
nohup python script_insert.py --cls hypertension > result_hypertension_insert.log 2>&1 &
# nohup python script_insert.py --cls agriculture > result_agriculture_insert.log 2>&1 &
# nohup python script_insert.py --cls cs > result_cs_insert.log 2>&1 &
# nohup python script_insert.py --cls legal > result_legal_insert.log 2>&1 &
# nohup python script_insert.py --cls mix > result_mix_insert.log 2>&1 &
```

### Step2. Retrieve Knowledge of HyperGraphRAG
```bash
python script_hypergraphrag.py --data_source hypertension
# python script_graphrag.py --data_source hypertension
# python script_standardrag.py --data_source hypertension
# python script_naivegeneration.py --data_source hypertension
```

### Step1b. Build Official GraphRAG Index
Before running the official `GraphRAG` baseline with the current local embedding default, expose the embedding model through an OpenAI-compatible endpoint and set:

```bash
export HGRAG_GRAPHRAG_EMBED_API_BASE=http://127.0.0.1:11434/v1
export HGRAG_GRAPHRAG_EMBED_MODEL=qwen3-embedding:0.6b
export HGRAG_GRAPHRAG_EMBED_API_KEY=ollama
python script_graphrag_index.py --data_source hypertension
```

### Step3. Generate Based on Retrieved Knowledge
```bash
python get_generation.py --data_sources hypertension --methods HyperGraphRAG
# python get_generation.py --data_sources hypertension --methods GraphRAG
# python get_generation.py --data_sources hypertension --methods StandardRAG
# python get_generation.py --data_sources hypertension --methods NaiveGeneration
```

### Step4. Evaluate the Generation
```bash
CUDA_VISIBLE_DEVICES=0 python get_score.py --data_source hypertension --method HyperGraphRAG
# CUDA_VISIBLE_DEVICES=0 python get_score.py --data_source hypertension --method GraphRAG
# CUDA_VISIBLE_DEVICES=0 python get_score.py --data_source hypertension --method StandardRAG
# CUDA_VISIBLE_DEVICES=0 python get_score.py --data_source hypertension --method NaiveGeneration
```

### Step5. See Evaluation Results
```bash
python see_score.py --data_source hypertension --method HyperGraphRAG
# python see_score.py --data_source hypertension --method GraphRAG
# python see_score.py --data_source hypertension --method StandardRAG
# python see_score.py --data_source hypertension --method NaiveGeneration
```
