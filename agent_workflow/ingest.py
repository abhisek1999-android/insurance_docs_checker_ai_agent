# ingest.py
import logging
import docx2txt
from pypdf import PdfReader
from agent_workflow.chunker import chunk_document

logger = logging.getLogger(__name__)

def parse_file(path: str) -> str:
    if path.lower().endswith(".docx"):
        return docx2txt.process(path)
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    # For other files, raise error
    raise ValueError("Unsupported file type. Please upload a PDF or DOCX file.")

def ingest_file(path: str):
    logger.info("ingest_file - parsing %s", path)
    text = parse_file(path)
    logger.info("ingest_file - extracted %d chars of text", len(text))
    chunks = chunk_document(text)
    logger.info("ingest_file - produced %d chunks", len(chunks))
    return chunks

if __name__=="__main__":
    import sys, json
    if len(sys.argv)<2:
        print("usage: python ingest.py <file>")
        raise SystemExit(1)
    chunks = ingest_file(sys.argv[1])
    print(f"Produced {len(chunks)} chunks")
    print(json.dumps(chunks[:2], indent=2))