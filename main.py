import os
from datetime import datetime
from dotenv import load_dotenv
from utils.logger import log_info, log_success, log_warning
from utils.state_manager import (
    initialize_temp_state,
    load_temp_state,
    save_state,
    save_temp_state,
    is_duplicate,
    add_processed_url,
)
from utils.gemini_helper import generate_summary
from utils.docx_generator import create_release_notes_doc
from utils.email_sender import send_email
from scrapers.scraper import scrape_all

def main():
    load_dotenv()
    log_info("Starting UTSA Digital Tools Release Notes Automation")
    
    state = initialize_temp_state()
    temp_state = load_temp_state()
    raw_notes = scrape_all()
    
    new_notes = []
    for note in raw_notes:
        if not is_duplicate(note['url'], state) and not is_duplicate(note['url'], temp_state):
            new_notes.append(note)
            add_processed_url(note['url'], state)
        else:
            log_warning(f"Already documented note skipped for {note['tool']}")

    if new_notes:
        log_info(f"Found {len(new_notes)} new release notes.")
        summary = generate_summary(new_notes)
        doc_path = create_release_notes_doc(new_notes, summary)
        send_email(doc_path)
    else:
        log_info("No new release notes found this run.")
        send_email(None) 
        
    state['last_run'] = datetime.now().isoformat()
    save_state(state)
    temp_state['processed_urls'] = list(dict.fromkeys(
        temp_state.get('processed_urls', []) + state.get('processed_urls', [])
    ))
    temp_state['last_run'] = state['last_run']
    save_temp_state(temp_state)
    log_success("Automation run completed successfully.")

if __name__ == "__main__":
    main()