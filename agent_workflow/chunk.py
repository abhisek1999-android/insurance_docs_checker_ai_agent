import re
import uuid
import json
from typing import List, Dict
from dataclasses import dataclass, asdict

# ==========================================================
# CONFIG
# ==========================================================

DOC_ID = "REGULATORY_ACT"
JURISDICTION = "India"
MAX_TOKENS = 500
OVERLAP_SENTENCES = 3

# Optional accurate token counter
try:
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text):
        return len(encoding.encode(text))
except:
    def count_tokens(text):
        return len(text.split())


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass
class Chunk:
    doc_id: str
    chunk_id: str
    structure_title: str   # CHAPTER I / PART II
    section_id: str        # 3 / 3A / 64VA
    subsection_id: str     # 1 / 2A
    clause_id: str         # a / aa / iii
    chunk_type: str        # section / subsection / clause
    text: str
    token_count: int


# ==========================================================
# TEXT NORMALIZATION
# ==========================================================

def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def remove_contents_if_present(text: str) -> str:
    """
    Removes duplicate heading/contents pages if detected.
    Keeps content from second occurrence of Act title.
    """
    matches = list(re.finditer(r"ACT[, ]+\d{4}", text, re.IGNORECASE))
    if len(matches) >= 2:
        return text[matches[1].start():]
    return text


# ==========================================================
# STRUCTURE SPLITTING (CHAPTER / PART)
# ==========================================================

STRUCTURE_PATTERN = r"\n\s*((?:CHAPTER|PART)\s+[IVXLC]+[A-Z]*)"

def split_structure(text: str):
    splits = re.split(STRUCTURE_PATTERN, text, flags=re.IGNORECASE)

    if len(splits) < 3:
        return [("FULL_DOCUMENT", text)]

    structured = []
    for i in range(1, len(splits), 2):
        title = splits[i].strip()
        content = splits[i + 1]
        structured.append((title, content))

    return structured


# ==========================================================
# SECTION SPLITTING
# Handles:
# 1.
# 3A.
# 6AA.
# 64VA.
# 64-VA.
# ==========================================================

SECTION_PATTERN = r"\n\s*(\d+[A-Z]{0,3}(?:\-?[A-Z]+)?\.)"

def split_sections(text: str):
    splits = re.split(SECTION_PATTERN, text)
    structured = []

    if len(splits) < 3:
        return []

    for i in range(1, len(splits), 2):
        section_id = splits[i].strip(". \n")
        content = splits[i + 1]
        structured.append((section_id, content))

    return structured


# ==========================================================
# SUBSECTION SPLITTING  (1), (2A)
# ==========================================================

SUBSECTION_PATTERN = r"(\(\d+[A-Z]?\))"

def split_subsections(text: str):
    splits = re.split(SUBSECTION_PATTERN, text)
    structured = []

    for i in range(1, len(splits), 2):
        subsection_id = splits[i].strip("()")
        content = splits[i + 1]
        structured.append((subsection_id, content))

    return structured


# ==========================================================
# CLAUSE SPLITTING  (a), (aa), (iii)
# ==========================================================

CLAUSE_PATTERN = r"(\([a-z]{1,3}\)|\([ivx]+\))"

def split_clauses(text: str):
    splits = re.split(CLAUSE_PATTERN, text)
    structured = []

    for i in range(1, len(splits), 2):
        clause_id = splits[i].strip("()")
        content = splits[i + 1]
        structured.append((clause_id, content))

    return structured


# ==========================================================
# TOKEN FALLBACK SPLITTER
# ==========================================================

def token_split(text: str):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = []
    tokens = 0

    for sentence in sentences:
        t = count_tokens(sentence)
        if tokens + t > MAX_TOKENS:
            chunks.append(" ".join(current))
            overlap = current[-OVERLAP_SENTENCES:]
            current = overlap + [sentence]
            tokens = count_tokens(" ".join(current))
        else:
            current.append(sentence)
            tokens += t

    if current:
        chunks.append(" ".join(current))

    return chunks


# ==========================================================
# MAIN CHUNK BUILDER
# ==========================================================

def build_chunks(raw_text: str) -> List[Dict]:

    raw_text = normalize_text(raw_text)
    raw_text = remove_contents_if_present(raw_text)

    structures = split_structure(raw_text)

    all_chunks = []

    for structure_title, structure_text in structures:

        sections = split_sections(structure_text)

        # Fallback if sections not detected
        if not sections:
            sections = [("FULL_SECTION", structure_text)]

        for section_id, section_text in sections:

            subsections = split_subsections(section_text)

            if not subsections:
                subsections = [(None, section_text)]

            for subsection_id, subsection_text in subsections:

                clauses = split_clauses(subsection_text)

                if not clauses:
                    clauses = [(None, subsection_text)]

                for clause_id, clause_text in clauses:

                    text_blocks = token_split(clause_text)

                    for block in text_blocks:
                        block = block.strip()
                        if not block:
                            continue

                        chunk = Chunk(
                            doc_id=DOC_ID,
                            chunk_id=str(uuid.uuid4()),
                            structure_title=structure_title,
                            section_id=section_id,
                            subsection_id=subsection_id,
                            clause_id=clause_id,
                            chunk_type=(
                                "clause" if clause_id
                                else "subsection" if subsection_id
                                else "section"
                            ),
                            text=block,
                            token_count=count_tokens(block)
                        )

                        all_chunks.append(asdict(chunk))

    return all_chunks


# ==========================================================
# EXECUTION
# ==========================================================

if __name__ == "__main__":

    from docx import Document

    doc = Document(r"indurance_docs\The_IRDA_Act_1999_Attachment-1.docx")
    raw_text = "\n".join([p.text for p in doc.paragraphs])
    print(f"Total characters in raw text: {len(raw_text)}")
    chunks = build_chunks(raw_text)

    print(f"Total chunks created: {len(chunks)}")

    import json
    with open(r"indurance_docs\the_irda_act_1999_attachment.json", "w", encoding="utf-8", errors="ignore") as f:
        json.dump(chunks, f, indent=2)