import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from scrapers.scraper import scrape_all
from utils.logger import log_error

load_dotenv()

app = FastAPI(title="UTSA Digital Tools Scraper API")

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    expected_key = os.getenv("SCRAPER_API_KEY")
    if not expected_key or api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/scrape")
def trigger_scrape(_: str = Security(verify_api_key)) -> dict:
    try:
        raw_results = scrape_all()

        current_results = []
        for item in raw_results:
            url = item.get("url")
            if not url:
                continue

            content = item.get("content", "")
            if any(
                error_text in content
                for error_text in (
                    "ERR_HTTP2_PROTOCOL_ERROR",
                    "This site can't be reached",
                )
            ):
                continue

            current_results.append(item)

        return {
            "status": "success",
            "count": len(current_results),
            "data": current_results,
        }
    except Exception as exc:
        log_error(f"API scrape failed: {exc}")
        raise HTTPException(status_code=500, detail="Scrape failed") from exc