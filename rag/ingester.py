# rag/ingester.py
import hashlib
from pathlib import Path
from typing import List

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "pentest_reports"
DB_PATH = "./rag/chroma_db"

MAX_FILE_COUNT      = 1000
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

def _load_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _load_markdown(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")



def _load_docx(path: str) -> str:
    doc = DocxDocument(path)
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _load_document(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return _load_pdf(path)
    elif ext in (".md", ".markdown", ".txt"):
        return _load_markdown(path)
    elif ext == ".docx":
        return _load_docx(path)
    raise ValueError(f"Formato no soportado: {ext}")


def _chunk_text(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + CHUNK_SIZE].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _doc_id(filepath: str, chunk_index: int) -> str:
    base = hashlib.sha256(filepath.encode()).hexdigest()
    return f"{base}_chunk{chunk_index}"


def ingest_reports(reports_dir: str = "./reports_source") -> None:
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    model = SentenceTransformer(EMBED_MODEL)

    reports_path = Path(reports_dir)
    files = (
        list(reports_path.glob("**/*.pdf")) +
        list(reports_path.glob("**/*.md")) +
        list(reports_path.glob("**/*.markdown")) +
        list(reports_path.glob("**/*.docx"))
    )

    if not files:
        print(f"[!] No se encontraron reportes en '{reports_dir}'")
        return

    if len(files) > MAX_FILE_COUNT:
        raise ValueError(f"Demasiados archivos: {len(files)} (máximo {MAX_FILE_COUNT})")

    for filepath in files:
        if filepath.stat().st_size > MAX_FILE_SIZE_BYTES:
            logger.warning("Archivo omitido por tamaño excesivo: %s", filepath.name)
            continue

        print(f"[+] Procesando: {filepath.name}")
        try:
            text = _load_document(str(filepath))
            chunks = _chunk_text(text)

            collection.upsert(
                ids=[_doc_id(str(filepath), i) for i in range(len(chunks))],
                embeddings=model.encode(chunks).tolist(),
                documents=chunks,
                metadatas=[
                    {"source": filepath.name, "chunk_index": i, "filepath": filepath.name}
                    for i in range(len(chunks))
                ]
            )
            print(f"    → {len(chunks)} fragmentos indexados")

        except Exception:
            logger.exception("Error procesando %s", filepath.name)

    print(f"\n[✓] Ingestión completa. Fragmentos en DB: {collection.count()}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_reports()
