# rag/ingester.py
import hashlib
from pathlib import Path
from typing import List
import logging
import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from docx import Document as DocxDocument
from pathlib import Path
import re
import unicodedata
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
# Sección que SÍ queremos extraer
START_SECTIONS = (
    "vulnerabilidades encontradas",
    "pruebas informativas"
)

# Secciones que cortan la captura (ruido que no aporta al estilo)
STOP_SECTIONS = (
    "glosario",
    "clasificacion segun su severidad",
    "clasificacion segun el esfuerzo",
    "resumen de hallazgos",
    "resumen grafico",
    "conclusiones",
    "anexos",
)

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



def _paragraph_text(paragraph) -> str:
    """Texto de un párrafo, convirtiendo <w:br>/<w:tab> en separadores.
    Ignora el texto de cuadros de texto anidados (se procesan como párrafos
    aparte), evitando duplicación."""
    p = paragraph._p
    txbx = qn("w:txbxContent")
    t_tag, tab_tag = qn("w:t"), qn("w:tab")
    br_tag, cr_tag = qn("w:br"), qn("w:cr")

    parts = []
    for node in p.iter():
        if node.tag not in (t_tag, tab_tag, br_tag, cr_tag):
            continue
        # ¿el nodo está dentro de un textbox anidado de ESTE párrafo?
        anc = node.getparent()
        dentro_textbox = False
        while anc is not None and anc is not p:
            if anc.tag == txbx:
                dentro_textbox = True
                break
            anc = anc.getparent()
        if dentro_textbox:
            continue
        if node.tag == t_tag:
            parts.append(node.text or "")
        elif node.tag == tab_tag:
            parts.append(" ")
        else:  # br o cr
            parts.append("\n")
    return "".join(parts)


def _load_docx(path: str) -> str:
    doc = DocxDocument(path)
    paras = list(_iter_all_paragraphs(doc))

    filtered = []
    capture = False
    for para in paras:
        text = _paragraph_text(para).strip()
        if not text:
            continue
        kind = _classify_heading(text)
        if kind == "start":
            capture = True
            continue
        if kind == "stop":
            capture = False
            continue
        if capture:
            filtered.append(text)

    if filtered:
        return "\n".join(filtered)

    # Salvaguarda: si no se detectó la sección, extrae todo y avisa
    logger.warning(
        "No se detectó 'Vulnerabilidades Encontradas' en %s; "
        "se extrae el documento completo.", Path(path).name
    )
    todo = []
    for para in paras:
        text = _paragraph_text(para).strip()
        if text:
            todo.append(text)
    return "\n".join(todo)

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

    model = SentenceTransformer(EMBED_MODEL, local_files_only=True)

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

def _normalize(text: str) -> str:
    """Normaliza un título: minúsculas, sin acentos, sin numeración inicial."""
    text = text.strip().lower()
    text = re.sub(r"^[\d\.\)\s]+", "", text)        # quita "11.1 ", "7. ", etc.
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"           # quita acentos
    )
    return text.strip()


def _classify_heading(text: str):
    """Clasifica un párrafo como inicio/fin de sección, ignorando entradas
    del índice (terminan en número de página) y párrafos largos (prosa)."""
    norm = _normalize(text)
    if re.search(r"\d+\s*$", norm):          # entrada de índice → ignorar
        return None
    if len(norm) > 100:                       # demasiado largo para ser título
        return None
    if any(norm.startswith(m) for m in START_SECTIONS):
        return "start"
    if any(norm.startswith(m) for m in STOP_SECTIONS):
        return "stop"
    return None

def _iter_all_paragraphs(doc):
    """Genera todos los <w:p> del documento en orden, incluyendo los que
    están dentro de cuadros de texto (text boxes), que python-docx ignora
    por defecto. Evita duplicados de bloques mc:Fallback (DrawingML/VML)."""
    mc_fallback = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
    for p in doc.element.body.iter(qn("w:p")):
        ancestro = p.getparent()
        en_fallback = False
        while ancestro is not None:
            if ancestro.tag == mc_fallback:
                en_fallback = True
                break
            ancestro = ancestro.getparent()
        if not en_fallback:
            yield Paragraph(p, doc)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_reports()
