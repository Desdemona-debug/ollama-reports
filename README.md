# report-writer

Generador inteligente de hallazgos y reportes de pentesting asistido por RAG (Retrieval-Augmented Generation).

Convierte ideas rápidas del operador en hallazgos técnicos formales, usando tus reportes anteriores como memoria de estilo, estructura y criterios de severidad.

---

## ¿Para qué sirve?

Durante un engagement de Red Team o Pentest, documentar hallazgos consume tiempo significativo. Este sistema resuelve dos problemas concretos:

1. **Velocidad:** en lugar de redactar desde cero, el operador escribe ideas crudas y el sistema genera el hallazgo formal completo.
2. **Consistencia:** todos los hallazgos siguen la misma estructura, tono y criterios de severidad, basados en tus reportes históricos.

### Flujo completo

```
ideas.txt (notas rápidas del operador)
       ↓
  Extracción de conceptos clave
       ↓
  Búsqueda en RAG (reportes anteriores)
       ↓
  Prompt enriquecido con contexto histórico
       ↓
  LLM local (qwen2.5:7b via Ollama)
       ↓
  Validación automática de calidad
       ↓
  Hallazgo formal en Markdown
```

---

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com) con el modelo `qwen2.5:7b` descargado
- Reportes anteriores en formato `.pdf` o `.md`

## Estructura del proyecto

```
report-writer/
├── input/
│   └── ideas.txt                        # Ideas crudas del operador
├── rag/
│   ├── ingester.py                      # Lee e indexa los reportes fuente
│   ├── retriever.py                     # Busca fragmentos relevantes en la DB
│   └── chroma_db/                       # Base de datos vectorial (auto-generada)
├── writer/
│   ├── prompt_builder.py                # Ensambla el prompt con contexto RAG
│   ├── report_generator.py              # Llama al LLM y devuelve el hallazgo
│   ├── validators.py                    # Valida calidad y estructura del output
│   └── template_renderer.py            # Aplica plantillas al hallazgo generado
├── templates/
│   ├── finding_template.md              # Plantilla base de hallazgo
│   └── executive_summary_template.md   # Plantilla de resumen ejecutivo
├── reports_source/                      # Tus reportes anteriores van aquí
└── main.py                              # Punto de entrada del sistema
```

---

## Descripción de módulos

### `rag/ingester.py`
Lee todos los archivos `.pdf` y `.md` de `reports_source/`, los divide en fragmentos de texto y los indexa como vectores en ChromaDB.

Solo se ejecuta una vez, o cada vez que se agreguen nuevos reportes a `reports_source/`.

Usa el modelo de embeddings `paraphrase-multilingual-MiniLM-L12-v2`, que funciona con texto en español e inglés sin necesidad de API externa.

---

### `rag/retriever.py`
Dado un texto de entrada (las ideas del operador), busca en ChromaDB los fragmentos más similares semánticamente.

Devuelve los fragmentos con su puntaje de relevancia y la fuente de origen, para que el prompt al LLM incluya contexto real de reportes anteriores.

---

### `writer/prompt_builder.py`
Ensambla el prompt final que recibe el LLM. Combina:
- Un system prompt fijo con el rol y las reglas del modelo.
- Los fragmentos recuperados del RAG como contexto de referencia.
- Las ideas del operador.
- La estructura de output esperada.

Incluye un fallback `build_prompt_no_rag()` para cuando la base de datos está vacía o se desactiva el RAG con `--no-rag`.

---

### `writer/report_generator.py`
Orquesta el flujo completo: recupera contexto del RAG, construye el prompt, llama a Ollama y devuelve el hallazgo generado.

Parámetros configurables en el archivo:
- `OLLAMA_MODEL`: modelo a usar (default `qwen2.5:7b`)
- `OLLAMA_HOST`: dirección del servidor Ollama (default `http://localhost:11434`)
- `temperature: 0.3`: valor bajo para mantener redacción técnica y consistente

---

### `writer/validators.py`
Analiza el texto generado por el LLM antes de guardarlo. Detecta:

| Tipo | Qué verifica |
|------|-------------|
| Error | Secciones obligatorias faltantes |
| Error | Severidad fuera del catálogo permitido |
| Error | Output demasiado corto o con patrones inválidos |
| Error | Modelo autoidentificándose como IA o rechazando generar |
| Warning | Campos `[PENDIENTE]` sin completar |
| Warning | Resumen ejecutivo fuera de rango de palabras |

Si hay errores, los adjunta al final del hallazgo para que el operador los corrija.

---

### `writer/template_renderer.py`
Aplica las plantillas de `templates/` a los datos del hallazgo. Rellena los campos con los valores generados y marca como `[PENDIENTE]` los que falten.

---

### `templates/finding_template.md`
Plantilla estándar para un hallazgo individual. Incluye todos los campos del reporte: título, descripción técnica, impacto, evidencia, recomendación, severidad y versión ejecutiva.

---

### `templates/executive_summary_template.md`
Plantilla para el resumen ejecutivo del engagement completo. Incluye tabla de hallazgos por severidad, resumen general y recomendaciones prioritarias.

---
## Notas importantes

- Los reportes en `reports_source/` se usan **solo como referencia de estilo**. El sistema no copia texto literal de ellos.
- La base de datos vectorial (`rag/chroma_db/`) persiste entre ejecuciones. Si se agregan nuevos reportes, se vuelve a ejecutar `ingest`.
- El sistema no almacena ni transmite reportes a servicios externos. Todo corre localmente.

---
