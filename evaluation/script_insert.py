import os
import json
import time
import traceback
from hypergraphrag import HyperGraphRAG
import argparse
from hypergraphrag.openai_config import ensure_openai_api_key, is_local_embed_model

ensure_openai_api_key()

def insert_text(rag, file_path):
    with open(file_path, mode="r", encoding="utf-8") as f:
        unique_contexts = json.load(f)

    retries = 0
    max_retries = 10
    while retries < max_retries:
        try:
            rag.insert(unique_contexts)
            break
        except Exception as e:
            retries += 1
            print(f"Insertion failed, retrying ({retries}/{max_retries}), error: {e}")
            traceback.print_exc()
            time.sleep(10)
    if retries == max_retries:
        print("Insertion failed after exceeding the maximum number of retries")

parser = argparse.ArgumentParser()
parser.add_argument("--cls", type=str, default="hypertension")
args = parser.parse_args()
cls = args.cls
WORKING_DIR = f"expr/{cls}"

if not os.path.exists(WORKING_DIR):
    os.makedirs(WORKING_DIR)

local_llm_max_async = int(os.getenv("HGRAG_INSERT_LLM_MAX_ASYNC", "8"))
remote_llm_max_async = int(os.getenv("HGRAG_INSERT_LLM_MAX_ASYNC", "32"))
entity_summary_llm_max_async = int(
    os.getenv("HGRAG_ENTITY_SUMMARY_LLM_MAX_ASYNC", "1")
)

rag_kwargs = {
    "working_dir": WORKING_DIR,
    "llm_model_max_async": remote_llm_max_async,
    "entity_summary_llm_max_async": entity_summary_llm_max_async,
}
if is_local_embed_model():
    rag_kwargs["embedding_func_max_async"] = 1
    rag_kwargs["embedding_batch_num"] = 8
    rag_kwargs["llm_model_max_async"] = local_llm_max_async
else:
    rag_kwargs["embedding_func_max_async"] = 32

rag = HyperGraphRAG(**rag_kwargs)

insert_text(rag, f"contexts/{cls}_contexts.json")
