# writer/prompt_builder.py
from typing import List, Dict

SYSTEM_PROMPT = """Eres un asistente especializado en redacción de reportes de ciberseguridad ofensiva.
Tu función es tomar ideas generales de un operador de Red Team/Pentest y convertirlas en hallazgos \
formales y profesionales.
Usa el contexto recuperado únicamente como referencia de estilo, estructura, terminología y criterios \
de severidad. No copies texto de reportes anteriores de forma literal.
Reglas:
- Mantén tono profesional y técnico.
- No inventes evidencia que no esté en las ideas del operador.
- Si falta información, márcala como [PENDIENTE].
- Evita lenguaje alarmista o especulativo.
- No reveles nombres de clientes ni datos sensibles del contexto recuperado."""

FINDING_TEMPLATE = """Genera un hallazgo formal con la siguiente estructura exacta:

## 1. Título del hallazgo
## 2. Descripción técnica
## 3. Impacto
## 4. Evidencia sugerida
## 5. Recomendación
## 6. Severidad (Crítica / Alta / Media / Baja / Informativa) con justificación breve
## 7. Versión ejecutiva (2-3 oraciones para audiencia no técnica)"""


def build_prompt(ideas: str, rag_context: str) -> Dict[str, str]:
    user_content = f"""Contexto recuperado de reportes anteriores:
{rag_context}

---

Ideas del operador:
{ideas.strip()}

---

{FINDING_TEMPLATE}"""

    return {
        "system": SYSTEM_PROMPT,
        "user": user_content
    }


def build_prompt_no_rag(ideas: str) -> Dict[str, str]:
    user_content = f"""Ideas del operador:
{ideas.strip()}

---

{FINDING_TEMPLATE}"""

    return {
        "system": SYSTEM_PROMPT,
        "user": user_content
    }
