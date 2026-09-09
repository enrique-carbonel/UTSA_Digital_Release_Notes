from dotenv import load_dotenv
from scrapers.scraper import scrape_all
from utils.logger import log_info, log_success, log_warning
from utils.gemini_helper import generate_summary
from utils.docx_generator import create_release_notes_doc
from utils.email_sender import send_email


def _notes_to_text(raw_notes) -> str:
    """generate_summary() expects a plain string prompt, not the list of dicts scrape_all() returns."""
    chunks = []
    for note in raw_notes:
        if note.get("is_table"):
            rows = "\n".join(" | ".join(row) for row in note.get("data", []))
            chunks.append(f"=== {note['tool']} ===\n{rows}")
        else:
            chunks.append(f"=== {note['tool']} ===\n{note.get('title', '')}\n{note.get('content', '')}")
    return "\n\n".join(chunks)


def run_scraper_workflow():
    load_dotenv()
    log_info("Starting UTSA Digital Tools Release Notes Automation")

    # Obtener todas las notas raspadas en tiempo real sin filtrar por duplicados
    raw_notes = scrape_all()

    if raw_notes:
        log_info(f"Processing {len(raw_notes)} release notes for document generation.")
        # Generar resumen IA y documento Word con TODAS las notas obtenidas
        summary = generate_summary(_notes_to_text(raw_notes))
        doc_path = create_release_notes_doc(raw_notes, summary)
        send_email(doc_path)
    else:
        log_warning("No release notes could be extracted from any tool.")
        summary = "No release notes were retrieved during this run."
        doc_path = create_release_notes_doc([], summary)
        send_email(None)
        
    log_success("Automation run completed successfully.")
    return doc_path