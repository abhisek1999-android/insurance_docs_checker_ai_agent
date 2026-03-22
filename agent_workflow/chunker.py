# chunker.py
import re, uuid
from typing import List, Dict

SECTION_PATTERN = r"\n\s*(\d+[A-Z]{0,3}(?:\-?[A-Z]+)?\.)"
SUBSECTION_PATTERN = r"(\(\d+[A-Z]?\))"
CLAUSE_PATTERN = r"(\([a-z]{1,3}\)|\([ivx]+\))"

def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text

def split_sections(text: str):
    parts = re.split(SECTION_PATTERN, text)
    if len(parts) < 3:
        return [("FULL", text)]
    out=[]
    for i in range(1, len(parts), 2):
        sec_id = parts[i].strip(". \n")
        body = parts[i+1]
        out.append((sec_id, body.strip()))
    return out

def split_subsections(section_text: str):
    parts = re.split(SUBSECTION_PATTERN, section_text)
    if len(parts) < 3:
        return [(None, section_text)]
    out=[]
    for i in range(1, len(parts), 2):
        sub_id = parts[i].strip("()")
        body = parts[i+1]
        out.append((sub_id, body.strip()))
    return out

def split_clauses(subsection_text: str):
    parts = re.split(CLAUSE_PATTERN, subsection_text)
    if len(parts) < 3:
        return [(None, subsection_text)]
    out=[]
    for i in range(1, len(parts), 2):
        clause_id = parts[i].strip("()")
        body = parts[i+1]
        out.append((clause_id, body.strip()))
    return out

def token_split(text: str, max_words: int = 400):
    words = text.split()
    chunks=[]
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i+max_words]))
    return chunks

def chunk_document(text: str) -> List[Dict]:
    text = normalize_text(text)
    sections = split_sections(text)
    chunks=[]
    for sec_id, sec_body in sections:
        subsections = split_subsections(sec_body)
        for sub_id, sub_body in subsections:
            clauses = split_clauses(sub_body)
            for clause_id, clause_body in clauses:
                parts = token_split(clause_body, max_words=350)
                for idx, part in enumerate(parts):
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "section_id": sec_id or "FULL",
                        "subsection_id": sub_id,
                        "clause_id": clause_id,
                        "part_index": idx,
                        "text": part.strip()
                    })
    return chunks