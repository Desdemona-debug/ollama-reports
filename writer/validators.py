# writer/validators.py
import re
from dataclasses import dataclass, field
from typing import List, Tuple

REQUIRED_SECTIONS = [
    "## 1. Título del hallazgo",
    "## 2. Descripción técnica",
    "## 3. Impacto",
    "## 4. Evidencia sugerida",
    "## 5. Recomendación",
    "## 6. Severidad",
    "## 7. Versión ejecutiva",
]

VALID_SEVERITIES = {"crítica", "alta", "media", "baja", "informativa"}

MAX_FINDING_LENGTH = 8000
MIN_FINDING_LENGTH = 300

FORBIDDEN_PATTERNS = [
    (r"\[nombre del cliente\]", "Placeholder de cliente sin reemplazar"),
    (r"\[empresa\]",            "Placeholder de empresa sin reemplazar"),
    (r"as an AI",               "El modelo se identificó como IA"),
    (r"como modelo de lenguaje", "El modelo se identificó como IA"),
    (r"no puedo",               "El modelo rechazó generar contenido"),
]


@dataclass
class ValidationResult:
    passed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str]   = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append("[ERRORES]")
            lines.extend(f"  ✗ {e}" for e in self.errors)
        if self.warnings:
            lines.append("[ADVERTENCIAS]")
            lines.extend(f"  ⚠ {w}" for w in self.warnings)
        if self.passed:
            lines.append("[✓] Hallazgo válido")
        return "\n".join(lines)


def _check_sections(text: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    for section in REQUIRED_SECTIONS:
        if section.lower() not in text.lower():
            errors.append(f"Sección faltante: '{section}'")
    return errors, warnings


def _check_severity(text: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    section_match = re.search(
        r"##\s*6\.\s*Severidad[^\n]*\n(.*?)(?=##|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    if section_match:
        severity_text = section_match.group(1).lower()
        found = any(s in severity_text for s in VALID_SEVERITIES)
        if not found:
            errors.append(
                f"Severidad no reconocida. Valores válidos: {', '.join(VALID_SEVERITIES)}"
            )
    return errors, warnings


def _check_pending_fields(text: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    matches = re.findall(r"\[PENDIENTE\]", text, re.IGNORECASE)
    if matches:
        warnings.append(f"El hallazgo tiene {len(matches)} campo(s) marcado(s) como [PENDIENTE]")
    return errors, warnings


def _check_length(text: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    length = len(text)
    if length < MIN_FINDING_LENGTH:
        errors.append(f"Hallazgo demasiado corto ({length} chars). Mínimo: {MIN_FINDING_LENGTH}")
    if length > MAX_FINDING_LENGTH:
        warnings.append(f"Hallazgo muy extenso ({length} chars). Considera dividirlo.")
    return errors, warnings


def _check_forbidden(text: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    for pattern, description in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            errors.append(f"Patrón no permitido detectado: {description}")
    return errors, warnings


def _check_executive_summary(text: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    match = re.search(
        r"##\s*7\.\s*Versión ejecutiva[^\n]*\n(.*?)(?=##|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    if match:
        summary = match.group(1).strip()
        word_count = len(summary.split())
        if word_count < 10:
            warnings.append(f"Versión ejecutiva muy corta ({word_count} palabras).")
        elif word_count > 100:
            warnings.append(f"Versión ejecutiva larga ({word_count} palabras). Idealmente < 50.")
    return errors, warnings


def validate(finding_text: str) -> ValidationResult:
    all_errors: List[str] = []
    all_warnings: List[str] = []

    checks = [
        _check_sections,
        _check_severity,
        _check_pending_fields,
        _check_length,
        _check_forbidden,
        _check_executive_summary,
    ]

    for check in checks:
        errors, warnings = check(finding_text)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    return ValidationResult(
        passed=len(all_errors) == 0,
        warnings=all_warnings,
        errors=all_errors
    )