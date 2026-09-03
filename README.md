# UTSA Digital Tools Release Notes

## Automatic Release Note Collection and Email Delivery

This project checks the release-note pages for UTSA digital tools, collects the newest updates, creates a plain-language summary, saves the results as a Word document, and emails the document to a list of recipients.

## What the System Does

When you run `main.py`, the system:

1. Loads its saved history.
2. Visits the supported vendors' release-note pages.
3. Keeps only URLs that have not already been processed.
4. Sends the new updates to Google Gemini for an executive summary.
5. Creates a Word document in the `RAW/` folder.
6. Emails the document to the recipients in `helper_files/recipients.csv`.
7. Saves the latest run and processed URLs for the next run.

If there are no new updates, the system sends an email saying that no new release notes were found.

## Requirements

- Python 3.10 or newer
- Google Chrome
- Internet access
- A Gemini API key
- An email account that can send mail through Gmail SMTP

Selenium uses Chrome to read pages that need a web browser. `webdriver-manager` is included to help manage the browser driver.

## Installation

Open a terminal in the project folder and run the commands for your operating system.

### macOS and Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Windows Command Prompt

```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

All paths in this project are relative to the project folder. The program finds its files from the location of the Python code at runtime, so it does not depend on a specific username, drive letter, or computer. Windows and macOS users can place the project in any local folder.

## Configuration

Create a file named `.env` in the main project folder. Do not commit this file because it contains private information.

```env
GEMINI_API_KEY=your_gemini_api_key
EMAIL_SENDER=your_email@gmail.com
EMAIL_APP_PASSWORD=your_gmail_app_password
SCRAPER_API_KEY=choose_a_long_random_api_key
```

One scraper also supports a login-protected tool:

```env
SS_USERNAME=your_username
SS_PASSWORD=your_password
```

The recipient list is stored in `helper_files/recipients.csv`. It must contain the columns `Email` and `Name`.

## Running the System

Activate the virtual environment, then run:

```bash
python main.py
```

Messages printed in the terminal show which pages were read, which updates were found, and whether the email was sent.

## API Service

The scraper can also be exposed to Agents through the FastAPI service. Start it from the project folder after installing the requirements:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Use `GET /health` for an unauthenticated health check. Use `POST /scrape` with the configured API key in the `X-API-KEY` header. The endpoint returns the current valid release notes as JSON on every request. It does not read or write the document-generation state, so an agent can retrieve the latest updates even when they were already included in a Word document.

## Output and Saved State

| Location | Purpose |
| --- | --- |
| `RAW/` | Generated Word documents containing the release notes |
| `config.json` | Main history of the last run and processed URLs |
| `temp_config.json` | Temporary URL history used by the Word-document workflow |
| `helper_files/gemini_prompt.txt` | Instructions used to create the AI summary |
| `helper_files/recipients.csv` | Email recipients |

Generated documents use this naming format:

```text
RAW/UTSA_Digital_Tools_Release_Notes_YYYYMMDD.docx
```

## Supported Tools

The current scraper list includes Adobe Creative Cloud, Anthology Ally, Canvas, Equidox, Gradescope, Padlet, Panopto, PlayPosit, ReadSpeaker, Respondus, Simple Syllabus, Turnitin, Qwickly, and Zoom.

## Common Problems

### No AI summary

Check that `GEMINI_API_KEY` exists in `.env` and is valid. The document can still be created, but it will use an unavailable-summary message.

### Email was not sent

Check `EMAIL_SENDER`, `EMAIL_APP_PASSWORD`, and `helper_files/recipients.csv`. Gmail requires an app password for many accounts; the regular account password may not work.

### A page could not be read

Some pages change their layout or require Chrome. The system logs the failed scraper and continues trying the other tools.

### An update is skipped

The Word-document workflow uses the source URL in `config.json` and `temp_config.json` to avoid documenting the same release twice. The agent-facing `/scrape` endpoint does not apply this check and always returns the current valid scrape results.

## AI Agent Notes

### Main Control Flow

- Start here: `main.py`
- Scraping logic: `scrapers/scraper.py`
- Duplicate tracking: `utils/state_manager.py`
- AI summary: `utils/gemini_helper.py`
- Word document creation: `utils/docx_generator.py`
- Email delivery: `utils/email_sender.py`

### Important Rules

- Keep secrets in environment variables, never in source code.
- Preserve the dictionary fields returned by scrapers: `tool`, `title`, `content`, and `url`.
- Table-based results may also use `is_table` and `data`.
- New documents must continue to be written to `RAW/`.
- A scraper failure should not stop the other scrapers from running.
- Update `requirements.txt` when adding a third-party package.
- Update this README when setup, environment variables, output paths, or supported tools change.

### Adding a New Scraper

1. Add a function in `scrapers/scraper.py`.
2. Return a result using the standard fields.
3. Add the function to the `scrapers` list inside `scrape_all()`.
4. Run `python main.py` and check the terminal output and generated document.

## Security Notes

Private files such as `.env`, recipient data, temporary state, logs, and generated documents are excluded by `.gitignore`. Review files before publishing the repository to make sure no API keys, passwords, or private email addresses are included.