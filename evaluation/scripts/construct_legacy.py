import json
from hypergraphrag import HyperGraphRAG
from hypergraphrag.openai_config import ensure_openai_api_key

ensure_openai_api_key()

rag = HyperGraphRAG(working_dir=f"expr/example")

with open(f"example_contexts.json", mode="r") as f:
    unique_contexts = json.load(f)
    
rag.insert(unique_contexts)
