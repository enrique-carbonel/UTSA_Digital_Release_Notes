import os
from pathlib import Path
from google import genai
from utils.logger import log_info, log_error
import json

PROMPT_FILE = Path(__file__).resolve().parent.parent / "helper_files" / "gemini_prompt.txt"
ROLE_FILE = Path(__file__).resolve().parent.parent / "helper_files" / "gemini_role_prompt.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")


def _extract_text_from_response(response):
    if response is None:
        return None
    text = getattr(response, "text", None)
    if text:
        return text
    text = getattr(response, "output", None) or getattr(response, "content", None)
    if text:
        return text
    candidates = getattr(response, "candidates", None)
    if candidates and len(candidates) > 0:
        first = candidates[0]
        return getattr(first, "output", None) or getattr(first, "content", None) or None
    try:
        return str(response)
    except Exception:
        return None


def _get_note_text(note):
    if note.get('is_table'):
        rows = note.get('data') or []
        if rows:
            formatted_rows = []
            for row in rows:
                cleaned = [str(cell).strip() for cell in row if str(cell).strip()]
                if cleaned:
                    formatted_rows.append(" | ".join(cleaned))
            return "\n".join(formatted_rows)

    return (
        note.get('content')
        or note.get('text')
        or note.get('summary')
        or note.get('title', '')
        or ''
    ).strip()


def generate_summary(prompt: str) -> str:
    """Llama a la API de Gemini y retorna el texto limpio."""
    try:
        log_info("Generating AI summary with Gemini...")
        
        # Instancia/Llamada al modelo Gemini
        response = model.generate_content(prompt)
        
        # IMPORTANTE: response.text es un string. 
        # Asegúrate de retornar directamente response.text y no hacerle un .get()
        if hasattr(response, 'text'):
            return response.text
        
        return str(response)

    except Exception as e:
        log_error(f"Failed to generate summary: {e}")
        return "Summary could not be generated."

def generate_role_summary(raw_text: str, user_group: str) -> str:
    """Carga los prompts por rol y llama a la API de Gemini."""
    try:
        # Cargar y parsear explícitamente a diccionario
        with open(ROLE_FILE, "r", encoding="utf-8") as f:
            prompts_dict = json.load(f)
        
        # Si por alguna razón sigue siendo string, forzar segundo json.loads
        if isinstance(prompts_dict, str):
            prompts_dict = json.loads(prompts_dict)

        # Buscar el prompt según el user_group
        selected_prompt = prompts_dict.get(user_group, prompts_dict.get("Admins", ""))
    except Exception as e:
        log_error(f"Error loading role_prompts.json: {e}")
        selected_prompt = "Extract and format the most relevant release notes."

    full_prompt = f"{selected_prompt}\n\n=== RAW RELEASE NOTES ===\n{raw_text}"
    
    # Invocar a Gemini
    return generate_summary(full_prompt)