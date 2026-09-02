import json
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / 'config.json'
TEMP_CONFIG_FILE = PROJECT_ROOT / 'temp_config.json'

def load_state():
    if not CONFIG_FILE.exists():
        return {"last_run": None, "processed_urls": []}
    with CONFIG_FILE.open('r') as f:
        return json.load(f)

def save_state(state):
    with CONFIG_FILE.open('w') as f:
        json.dump(state, f, indent=4)

def initialize_temp_state():
    state = load_state()
    if not TEMP_CONFIG_FILE.exists():
        with TEMP_CONFIG_FILE.open('w') as f:
            json.dump(state, f, indent=4)

        state['processed_urls'] = []
        save_state(state)
    return state

def load_temp_state():
    if not TEMP_CONFIG_FILE.exists():
        return {"last_run": None, "processed_urls": []}
    with TEMP_CONFIG_FILE.open('r') as f:
        return json.load(f)

def save_temp_state(state):
    with TEMP_CONFIG_FILE.open('w') as f:
        json.dump(state, f, indent=4)

def is_duplicate(url, state):
    return url in state.get('processed_urls', [])

def add_processed_url(url, state):
    if url not in state.setdefault('processed_urls', []):
        state['processed_urls'].append(url)

def get_cutoff_date(state):
    last_run = state.get('last_run')
    if last_run:
        return datetime.fromisoformat(last_run)
    return datetime.now() - timedelta(days=30)