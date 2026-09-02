import os
from pathlib import Path
from google import genai
from utils.logger import log_info, log_error

PROMPT_FILE = Path(__file__).resolve().parent.parent / "helper_files" / "gemini_prompt.txt"


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


def generate_summary(release_notes_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log_error("Gemini API key not found. Skipping AI summary.")
        return "AI Summary unavailable (No API Key)."

    try:
        log_info("Generating AI summary with Gemini...")
        client = genai.Client(api_key=api_key)

        prompt = PROMPT_FILE.read_text(encoding="utf-8").rstrip() + "\n\n"
        for item in release_notes_data:
            note_text = _get_note_text(item)
            tool_name = item.get('tool', 'Unknown tool')
            title = item.get('title', 'Untitled update')
            prompt += f"Tool: {tool_name}\nTitle: {title}\nUpdate: {note_text[:500]}...\n\n"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        text = _extract_text_from_response(response)
        return text or "Summary could not be generated."
    except Exception as e:
        log_error(f"Failed to generate summary: {e}")
        return "Summary could not be generated."