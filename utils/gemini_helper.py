import os
import json
from pathlib import Path
from google import genai
from google.genai import types
from pydantic import BaseModel
from utils.logger import log_info, log_error

# Rutas relativas a la carpeta helper_files
HELPER_DIR = Path(__file__).resolve().parent.parent / "helper_files"
ROLE_FILE = HELPER_DIR / "gemini_role_prompt.json"
SYSTEM_INSTRUCTION_FILE = HELPER_DIR / "gemini_system_instruction.txt"

# Cliente oficial de Google GenAI
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

class RoleSummarySchema(BaseModel):
    executive_summary: str
    detailed_tool_updates: str


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


def generate_summary(prompt: str, json_mode: bool = False, response_schema=None) -> str:
    """Invoca la API de Gemini 2.5 Flash."""
    try:
        log_info("Generating AI response with Gemini 2.5 Flash...")

        config = (
            types.GenerateContentConfig(response_mime_type="application/json", response_schema=response_schema)
            if json_mode
            else None
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config,
        )

        extracted_text = _extract_text_from_response(response)
        return extracted_text.strip() if extracted_text else "Summary could not be generated."
    except Exception as e:
        log_error(f"Failed to generate summary: {e}")
        return "Summary could not be generated."


# Alias para tolerar variaciones en el valor que manda Power Automate / Copilot Studio
# (singular vs plural, minusculas, "IT Support", etc.) en vez de caer siempre en Admins.
ROLE_ALIASES = {
    "admin": "Admins",
    "admins": "Admins",
    "administrator": "Admins",
    "executive": "Executives",
    "executives": "Executives",
    "leadership": "Executives",
    "designer": "Designers",
    "designers": "Designers",
    "instructional designer": "Designers",
    "tech support": "Tech Support",
    "techsupport": "Tech Support",
    "tech_support": "Tech Support",
    "it support": "Tech Support",
    "support": "Tech Support",
}


def _resolve_role_key(user_group: str, prompts_dict: dict) -> str:
    if not user_group:
        return "Admins"
    normalized = user_group.strip().lower()
    for key in prompts_dict:
        if key.lower() == normalized:
            return key
    return ROLE_ALIASES.get(normalized, "Admins")


def generate_role_summary(raw_text: str, user_group: str) -> dict:
    """Carga las instrucciones puras desde el archivo JSON sin hardcodear prompts en Python.

    Regresa un dict con "executive_summary" y "detailed_tool_updates" por separado,
    ya que la plantilla de Word tiene un content control distinto para cada sección.
    """
    try:
        with open(ROLE_FILE, "r", encoding="utf-8") as f:
            prompts_dict = json.load(f)

        role_key = _resolve_role_key(user_group, prompts_dict)
        if role_key != user_group:
            log_info(f"user_group '{user_group}' resolved to role '{role_key}'")
        role_config = prompts_dict.get(role_key, prompts_dict.get("Admins"))
        instructions_json = json.dumps(role_config, indent=2)

    except Exception as e:
        log_error(f"Error loading role_prompts.json: {e}")
        instructions_json = "Extract and format all release notes present in the document."

    log_info(f"generate_role_summary: user_group='{user_group}', raw_text length={len(raw_text)}")
    log_info(f"raw_text preview: {raw_text[:300]!r}")

    full_prompt = (
        f"INSTRUCTIONS AND ROLE CONFIGURATION:\n"
        f"{instructions_json}\n\n"
        f"IMPORTANT: Base your summary strictly on the RAW INPUT DOCUMENT below. "
        f"If the document mentions any digital tool, product, or service update at all "
        f"(even one not on the recognized_tools list), you MUST summarize it under its own "
        f"heading using the name as it appears in the text - do not skip it just because it "
        f"is unfamiliar. Only respond that there are no relevant updates if the RAW INPUT "
        f"DOCUMENT section below is empty or contains no tool/product-related text whatsoever.\n\n"
        f"Respond with ONLY a JSON object with exactly two keys: \"executive_summary\" and "
        f"\"detailed_tool_updates\". Each value is the Markdown body text for that section only "
        f"(use ## for each tool name as a sub-heading inside detailed_tool_updates). Do NOT "
        f"include a top-level '#' section title in either value - the Word template already "
        f"has that heading. Do NOT ask the reader questions or add closing remarks; this is a "
        f"formal document, not a chat reply.\n\n"
        f"=== RAW INPUT DOCUMENT ===\n"
        f"{raw_text}"
    )

    result = generate_summary(full_prompt, json_mode=True, response_schema=RoleSummarySchema)
    log_info(f"generate_role_summary: Gemini response length={len(result)}")

    try:
        data = json.loads(result)
        return {
            "executive_summary": str(data.get("executive_summary", "")).strip(),
            "detailed_tool_updates": str(data.get("detailed_tool_updates", "")).strip(),
        }
    except Exception as e:
        log_error(f"Gemini did not return valid JSON, returning raw text instead: {e}")
        return {"executive_summary": result, "detailed_tool_updates": ""}