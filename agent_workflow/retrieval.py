# retrieval.py
import os, logging

logger = logging.getLogger(__name__)
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone import Pinecone
import json
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

client = ChatGroq(api_key=os.getenv("GROQ_API_KEY"), model=os.getenv("LLM_MODEL", "gpt-4o"))

def embed_text(text):
    model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return model.embed_query(text)

def init_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index(os.getenv("PINECONE_INDEX_NAME"))

def coarse_retrieve(query, top_k=20, doc_filter=None):
    logger.info("coarse_retrieve - query=%s, top_k=%d", query[:80], top_k)
    idx = init_index()
    q_emb = embed_text(query)
    params = {"vector": q_emb, "top_k": top_k, "include_metadata": True}
    if doc_filter:
        params["filter"] = doc_filter
    res = idx.query(**params)
    logger.info("coarse_retrieve - got %d matches from Pinecone", len(res["matches"]))
    return res["matches"]

def rerank_with_llm(query, candidates, top_n=5):
    logger.info("rerank_with_llm - reranking %d candidates, top_n=%d", len(candidates), top_n)
    scored=[]
    for c in candidates:
        snippet = c["metadata"]["text"]
        prompt = (
            f"On scale 0-1, rate how relevant the snippet is to the query. "
            f"Return only JSON: {{'score': <0-1>}}.\n\nQuery:\n{query}\n\nSnippet:\n{snippet}"
        )
        resp = client.invoke(prompt)
        try:
            j = json.loads(resp.content)
            score = float(j.get("score", 0))
        except Exception:
            score = 0.0
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    logger.info("rerank_with_llm - top scores: %s", [round(s, 3) for s, _ in scored[:top_n]])
    return [c for s,c in scored[:top_n]]