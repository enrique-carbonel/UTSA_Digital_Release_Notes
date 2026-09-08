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


def generate_role_summary(raw_text: str, user_group: str) -> dict:
    """
    Carga los prompts desde la carpeta helper_files, consulta a Gemini 2.5 Flash 
    y retorna un diccionario estructurado listo para la plantilla de Word.
    """
    # 1. Cargar el prompt específico del rol desde gemini_role_prompt.json
    selected_role_prompt = ""
    try:
        if ROLE_FILE.exists():
            with open(ROLE_FILE, "r", encoding="utf-8") as f:
                prompts_dict = json.load(f)
                if isinstance(prompts_dict, str):
                    prompts_dict = json.loads(prompts_dict)
                selected_role_prompt = prompts_dict.get(user_group, prompts_dict.get("Admins", ""))
    except Exception as e:
        log_error(f"Error loading {ROLE_FILE.name}: {e}")

    if not selected_role_prompt:
        selected_role_prompt = f"Process all tool release notes for the target audience: {user_group}."

    # 2. Cargar el template de instrucciones desde gemini_system_instruction.txt
    system_instruction_template = ""
    try:
        if SYSTEM_INSTRUCTION_FILE.exists():
            with open(SYSTEM_INSTRUCTION_FILE, "r", encoding="utf-8") as f:
                system_instruction_template = f.read()
    except Exception as e:
        log_error(f"Error loading {SYSTEM_INSTRUCTION_FILE.name}: {e}")

    if not system_instruction_template:
        system_instruction_template = "Return JSON with 'executive_summary' and 'detailed_tool_updates'.\n\n{raw_text}"

    # 3. Armar el prompt final combinando el Rol + Instrucción de formato + Texto Raw
    formatted_instruction = system_instruction_template.replace("{raw_text}", raw_text)
    full_prompt = f"{selected_role_prompt}\n\n{formatted_instruction}"

    # 4. Enviar a Gemini y procesar respuesta
    raw_response = generate_summary(full_prompt)

    # Limpiar formato markdown (```json ... ```) si viene envuelto
    clean_json_str = raw_response.replace("```json", "").replace("```", "").strip()

    try:
        formatted_data = json.loads(clean_json_str)
        return {
            "executive_summary": formatted_data.get("executive_summary", ""),
            "detailed_tool_updates": formatted_data.get("detailed_tool_updates", clean_json_str)
        }
    except Exception as e:
        log_error(f"Failed to parse JSON response from Gemini, using raw response fallback: {e}")
        return {
            "executive_summary": f"Release Notes Briefing for {user_group}",
            "detailed_tool_updates": raw_response
        }