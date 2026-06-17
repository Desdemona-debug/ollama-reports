# writer/report_generator.py
import logging

import ollama

from rag.retriever import Retriever
from writer.prompt_builder import build_prompt, build_prompt_no_rag
from writer.validators import validate

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_HOST = "http://localhost:11434"


class ReportGenerator:
    def __init__(self, use_rag: bool = True):
        self.use_rag = use_rag
        self.retriever = Retriever() if use_rag else None
        self.client = ollama.Client(host=OLLAMA_HOST)

    def generate(self, ideas: str, top_k: int = 5) -> str:
        if self.use_rag and self.retriever:
            fragments = self.retriever.search(ideas, top_k=top_k)
            rag_context = self.retriever.format_context(fragments)
            prompt = build_prompt(ideas, rag_context)
            sources = [f["source"] for f in fragments]
        else:
            prompt = build_prompt_no_rag(ideas)
            sources = []

        response = self.client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user",   "content": prompt["user"]},
            ],
            options={
                "temperature": 0.3,
                "top_p": 0.9,
                "num_ctx": 8192,
            }
        )

        result = response.message.content

        if sources:
            unique_sources = list(dict.fromkeys(sources))
            logger.info("RAG sources consultadas: %s", ", ".join(unique_sources))

        validation = validate(result)
        if not validation.passed:
            logger.warning("Validación fallida: %s", validation.summary())
            result = (
                "> ⚠️ **ADVERTENCIA: este hallazgo no pasó la validación "
                "automática de calidad. Revísalo manualmente antes de usarlo.**\n\n"
                + result
            )

        return result

    def generate_from_file(self, filepath: str, top_k: int = 5) -> str:
        with open(filepath, "r", encoding="utf-8") as f:
            ideas = f.read()
        return self.generate(ideas, top_k=top_k)