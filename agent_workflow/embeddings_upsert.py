# embeddings_upsert.py
import json, time
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

client = ChatGroq(api_key=API_KEY, model=LLM_MODEL)

def get_embedding(text: str):
    model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return model.embed_query(text)

def init_pinecone():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME")
    existing = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing:
        pc.create_index(
            name=index_name,
            dimension=384,  # adjust dimension if model differs
            spec=ServerlessSpec(cloud="aws", region=os.getenv("PINECONE_ENV", "us-east-1")),
        )
    return pc.Index(index_name)

def upsert_chunks(chunks):
    idx = init_pinecone()
    batch=[]
    for c in chunks:
        emb = get_embedding(c["text"])
        meta = {
            "chunk_id": c["chunk_id"],
            "section_id": c["section_id"],
            "subsection_id": c["subsection_id"],
            "clause_id": c["clause_id"],
            "text": c["text"],
            "source": "user_upload"
        }
        batch.append((c["chunk_id"], emb, meta))
        if len(batch)>=100:
            idx.upsert(vectors=batch)
            batch=[]
    if batch:
        idx.upsert(vectors=batch)
    print("Upsert done")