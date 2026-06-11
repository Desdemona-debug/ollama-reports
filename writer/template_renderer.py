# writer/template_renderer.py
import string
from pathlib import Path
from datetime import date
from typing import Dict

TEMPLATES_DIR = Path("./templates")

def _load_template(filename: str) -> str:
    path = TEMPLATES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Plantilla no encontrada: {path}")
    return path.read_text(encoding="utf-8")

def _render(template_str: str, fields: Dict[str, str]) -> str:
    normalized = template_str.replace("{{", "${").replace("}}", "}")
    tmpl = string.Template(normalized)
    return tmpl.safe_substitute(fields)

def render_finding(fields: Dict[str, str]) -> str:
    template = _load_template("finding_template.md")
    defaults = {
        "titulo":                 "[PENDIENTE]",
        "fecha":                  date.today().isoformat(),
        "nombre_evaluacion":      "[PENDIENTE]",
        "severidad":              "[PENDIENTE]",
        "descripcion":            "[PENDIENTE]",
        "impacto":                "[PENDIENTE]",
        "evidencia":              "[PENDIENTE]",
        "recomendacion":          "[PENDIENTE]",
        "justificacion_severidad":"[PENDIENTE]",
        "version_ejecutiva":      "[PENDIENTE]",
        "fuentes":                "N/A",
    }
    defaults.update(fields)
    return _render(template,defaults)


def render_executive_summary(fields: Dict[str, str]) -> str:
    template = _load_template("executive_summary_template.md")
    defaults = {
        "nombre_evaluacion":          "[PENDIENTE]",
        "fecha":                      date.today().isoformat(),
        "cliente":                    "[PENDIENTE]",
        "alcance":                    "[PENDIENTE]",
        "resumen_general":            "[PENDIENTE]",
        "count_critica":              "0",
        "count_alta":                 "0",
        "count_media":                "0",
        "count_baja":                 "0",
        "count_informativa":          "0",
        "total_hallazgos":            "0",
        "hallazgos_principales":      "[PENDIENTE]",
        "recomendaciones_prioritarias":"[PENDIENTE]",
    }
    defaults.update(fields)
    return _render(template, defaults)