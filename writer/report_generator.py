from typing import Optional

import ollama

from rag.retriever import Retriever
from writer.prompt_builder import build_prompt, build_prompt_no_rag
from writer.validators import validate
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
            result += f"\n\n---\n_Fuentes consultadas: {', '.join(unique_sources)}_"

        validation = validate(result)
        if not validation.passed:
            # Adjunta advertencias al output para que el operador las vea
            result += f"\n\n---\n**Validación:**\n```\n{validation.summary()}\n```"

        return result

    def generate_from_file(self, filepath: str, top_k: int = 5) -> str:
        with open(filepath, "r", encoding="utf-8") as f:
            ideas = f.read()
        return self.generate(ideas, top_k=top_k)