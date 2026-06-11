import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from writer.report_generator import ReportGenerator

console = Console()
MAX_INPUT_CHARS = 50_000

def _validate_path(user_path: str, allowed_base: Path, label: str) -> Path:
    resolved = Path(user_path).resolve()
    if not str(resolved).startswith(str(allowed_base.resolve())):
        raise ValueError(f"{label} fuera del directorio permitido: {user_path}")
    return resolved

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generador de hallazgos de pentest asistido por RAG"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Comando: ingest
    ingest_parser = subparsers.add_parser("ingest", help="Indexar reportes anteriores")
    ingest_parser.add_argument(
        "--dir", default="./reports_source",
        help="Directorio con los reportes fuente (default: ./reports_source)"
    )

    # Comando: generate
    gen_parser = subparsers.add_parser("generate", help="Generar un hallazgo formal")
    gen_group = gen_parser.add_mutually_exclusive_group(required=True)
    gen_group.add_argument("--ideas", type=str, help="Ideas directamente como texto")
    gen_group.add_argument("--file",  type=str, help="Ruta a archivo .txt con las ideas")
    gen_parser.add_argument("--no-rag", action="store_true", help="Generar sin consultar el RAG")
    gen_parser.add_argument("--top-k", type=int, default=5, help="Fragmentos RAG a recuperar")
    gen_parser.add_argument("--output", type=str, help="Guardar resultado en archivo .md")

    return parser.parse_args()

def cmd_ingest(args):
    from rag.ingester import ingest_reports
    INGEST_BASE = Path.cwd() / "reports_source"

    try:
        safe_dir = _validate_path(args.dir, INGEST_BASE, "--dir")
    except ValueError as e:
        console.print(f"[red][!] {e}[/red]")
        sys.exit(1)

    console.print(Panel("[bold cyan]Iniciando ingestión de reportes...[/bold cyan]"))
    ingest_reports(reports_dir=str(safe_dir))

def cmd_generate(args):
    use_rag = not args.no_rag

    INPUT_DIR  = Path.cwd() / "input"
    OUTPUT_DIR = Path.cwd() / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Límites de tamaño de input
    if args.ideas and len(args.ideas) > MAX_INPUT_CHARS:
        console.print("[red][!] --ideas supera el límite de caracteres permitido.[/red]")
        sys.exit(1)
    if args.file and Path(args.file).exists():
        if Path(args.file).stat().st_size > MAX_INPUT_CHARS:
            console.print("[red][!] --file supera el tamaño máximo permitido.[/red]")
            sys.exit(1)

    console.print(Panel(
        f"[bold cyan]Generando hallazgo[/bold cyan] | "
        f"RAG: {'[green]ON[/green]' if use_rag else '[yellow]OFF[/yellow]'} | "
        f"top-k: {args.top_k}"
    ))

    generator = ReportGenerator(use_rag=use_rag)

    if args.file:
        try:
            safe_path = _validate_path(args.file, INPUT_DIR, "--file")
        except ValueError as e:
            console.print(f"[red][!] {e}[/red]")
            sys.exit(1)
        if not safe_path.exists():
            console.print(f"[red][!] Archivo no encontrado: {args.file}[/red]")
            sys.exit(1)
        result = generator.generate_from_file(str(safe_path), top_k=args.top_k)
    else:
        result = generator.generate(args.ideas, top_k=args.top_k)

    console.print("\n")
    console.print(Markdown(result))

    if args.output:
        try:
            safe_out = _validate_path(args.output, OUTPUT_DIR, "--output")
        except ValueError as e:
            console.print(f"[red][!] {e}[/red]")
            sys.exit(1)
        safe_out.write_text(result, encoding="utf-8")
        console.print(f"\n[green][✓] Resultado guardado en: {safe_out}[/green]")

def main():
    logging.basicConfig(
        filename="report-writer.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    args = parse_args()

    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "generate":
        cmd_generate(args)

if __name__ == "__main__":
    main()