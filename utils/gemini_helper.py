import os
import json
from pathlib import Path
from google import genai
from utils.logger import log_info, log_error

# Rutas relativas a la carpeta helper_files
HELPER_DIR = Path(__file__).resolve().parent.parent / "helper_files"
ROLE_FILE = HELPER_DIR / "gemini_role_prompt.json"
SYSTEM_INSTRUCTION_FILE = HELPER_DIR / "gemini_system_instruction.txt"

# Cliente oficial de Google GenAI
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def _extract_text_from_response(response) -> str:
    """Extrae el texto de la respuesta de Gemini de forma directa."""
    if not response:
        return ""
    if hasattr(response, "text") and response.text:
        return response.text
    try:
        return str(response)
    except Exception:
        return ""


def generate_summary(prompt: str) -> str:
    """Invoca la API de Gemini 2.5 Flash."""
    try:
        log_info("Generating AI response with Gemini 2.5 Flash...")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        extracted_text = _extract_text_from_response(response)
        return extracted_text.strip() if extracted_text else "Summary could not be generated."
    except Exception as e:
        log_error(f"Failed to generate summary: {e}")
        return "Summary could not be generated."


def generate_role_summary(raw_text: str, user_group: str) -> str:
    """Carga las instrucciones puras desde el archivo JSON sin hardcodear prompts en Python."""
    try:
        with open(ROLE_FILE, "r", encoding="utf-8") as f:
            prompts_dict = json.load(f)

        # Seleccionar la configuración del grupo o usar Admins por defecto
        role_config = prompts_dict.get(user_group, prompts_dict.get("Admins"))
        instructions_json = json.dumps(role_config, indent=2)

    except Exception as e:
        log_error(f"Error loading role_prompts.json: {e}")
        instructions_json = "Extract and format all release notes present in the document."

    full_prompt = (
        f"INSTRUCTIONS AND ROLE CONFIGURATION:\n"
        f"{instructions_json}\n\n"
        f"=== RAW INPUT DOCUMENT ===\n"
        f"{raw_text}"
    )
    
    return generate_summary(full_prompt)