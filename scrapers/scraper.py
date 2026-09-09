import requests
from bs4 import BeautifulSoup
import feedparser
import time
import re
from utils.logger import log_info, log_error, log_warning
import os

# --- Helper Functions ---

def get_soup(url, auth=None):
    """Fetches HTML from a URL using standard HTTP requests and returns a BeautifulSoup object."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    try:
        response = requests.get(url, headers=headers, auth=auth, timeout=25)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        log_error(f"Failed to fetch HTML for {url}: {e}")
        return None

def extract_content(soup, css_selectors):
    """Attempts to find content using specific selectors. Cleans out junk."""
    for selector in css_selectors:
        element = soup.select_one(selector)
        if element:
            for junk in element(["nav", "footer", "script", "style", "header", "aside"]):
                junk.decompose()
            return element.get_text(separator="\n").strip()
    
    # FOOLPROOF FALLBACK
    if soup.body:
        for junk in soup(["script", "style", "nav", "footer", "header", "aside"]):
            junk.decompose()
        return soup.body.get_text(separator="\n").strip()
        
    return "Content not found."

def parse_html_with_tables(html_content):
    """Converts HTML content to text, ensuring tables are formatted cleanly into plain text."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for table in soup.find_all('table'):
        table_text = []
        for row in table.find_all('tr'):
            cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
            if cells:
                table_text.append(" | ".join(cells))
                
        if table_text:
            new_text = soup.new_string("\n\n" + "\n".join(table_text) + "\n\n")
            table.replace_with(new_text)
            
    text = soup.get_text(separator="\n").strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

# --- Refactored Individual Scrapers (No Selenium) ---

def scrape_adobe():
    url = "https://helpx.adobe.com/creative-cloud/apps/whats-new/release-notes.html"
    log_info(f"Scraping Adobe CC: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        content = extract_content(soup, ["main", "article", ".page-content", "body"])
        return {"tool": "Adobe Creative Cloud", "title": "Latest Creative Cloud Updates", "content": content, "url": url}
    except Exception as e:
        log_error(f"Adobe CC scrape failed: {e}")
        return None

def scrape_ally():
    url = "https://help.anthology.com/ally-lms/en/administrators/whats-new/2026-release-notes.html"
    log_info(f"Scraping Anthology Ally: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        content = extract_content(soup, ['main', 'div[role="main"]', 'div.body-container'])
        matches = list(re.finditer(r'(Ally\s\d+\.\d+\.\d+\s*Release to production:)', content))
        if len(matches) >= 2:
            content = content[matches[0].start() : matches[1].start()]
        elif len(matches) == 1:
            content = content[matches[0].start() :]
            
        return {"tool": "Ally Accessibility Checker", "title": "Ally Latest Release", "content": content.strip(), "url": url}
    except Exception as e:
        log_error(f"Ally scrape failed: {e}")
    return None

def scrape_canvas():
    index_url = "https://community.instructure.com/en/categories/canvas-release-notes"
    base_domain = "https://community.instructure.com"
    log_info(f"Scraping Canvas: Discovering latest links at {index_url}")
    
    soup = get_soup(index_url)
    if not soup: return None
    
    try:
        # Phase 1: Discover URLs
        release_url = None
        deploy_url = None
        
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            full_href = href if href.startswith('http') else base_domain + href
            
            if "Canvas Release Notes (20" in text and not release_url:
                release_url = full_href
            elif "Canvas Deploy Notes (20" in text and not deploy_url:
                deploy_url = full_href
                
        # Phase 2: Content Extraction
        content_selectors = [".lia-message-body-content", ".Message-body", "article", ".article-content", "main"]
        
        release_content, release_title = "", "Latest Release"
        if release_url:
            r_soup = get_soup(release_url)
            if r_soup:
                body_elem = next((r_soup.select_one(s) for s in content_selectors if r_soup.select_one(s)), r_soup.body)
                release_content = parse_html_with_tables(str(body_elem))
                if r_soup.title: release_title = r_soup.title.text.split('-')[0].strip()

        deploy_content, deploy_title = "", "Latest Deploy"
        if deploy_url:
            d_soup = get_soup(deploy_url)
            if d_soup:
                body_elem = next((d_soup.select_one(s) for s in content_selectors if d_soup.select_one(s)), d_soup.body)
                deploy_content = parse_html_with_tables(str(body_elem))
                if d_soup.title: deploy_title = d_soup.title.text.split('-')[0].strip()

        combined_content = f"=== {release_title} ===\n{release_content}\n\n=== {deploy_title} ===\n{deploy_content}"
        
        if not release_content and not deploy_content:
            return {"tool": "Canvas", "title": "Canvas Notes", "content": "Could not extract full pages.", "url": index_url}
            
        return {
            "tool": "Canvas",
            "title": "Canvas Release & Deploy Notes",
            "content": combined_content,
            "url": index_url
        }
    except Exception as e:
        log_error(f"Canvas deep scrape failed: {e}")
        return None

def scrape_equidox():
    url = "https://www.app2.equidox.co/#/login"
    log_info(f"Scraping Equidox: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        content = extract_content(soup, ["div.release-notes", "mat-dialog-content", "body"])
        if "Equidox" in content and "Live!" in content:
            content = content[content.find("Equidox"):]
        return {"tool": "Equidox", "title": "Equidox Updates", "content": content, "url": url}
    except Exception as e:
        log_error(f"Equidox scrape failed: {e}")
    return None

def scrape_gradescope():
    url = "https://guides.gradescope.com/hc/en-us/articles/27893715730829-Gradescope-Release-Notes"
    log_info(f"Scraping Gradescope: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        body = soup.find('div', class_='article-body')
        if not body: return None
        text = body.get_text(separator="\n").strip()
        pattern = r'(202\d\s[A-Z][a-z]+\s\d{1,2}(?:st|nd|rd|th)?.*?)(?=\n\n|\n[A-Z][a-z]+\s202\d|\Z)'
        match = re.search(pattern, text, re.DOTALL)
        content = match.group(1).strip() if match else text
        return {"tool": "Gradescope", "title": "Latest Gradescope Update", "content": content, "url": url}
    except Exception as e:
        log_error(f"Gradescope scrape failed: {e}")
    return None

def scrape_padlet():
    url = "https://padlet.com/padlets/padlet-changelog-aft232zazwoplc0c"
    log_info(f"Scraping Padlet: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        card = soup.select_one("article, div.post-container, div[data-testid='post']")
        if card:
            content = card.get_text(separator="\n").strip()
            status = "Beta" if "beta" in content.lower() else "Released"
            return {"tool": "Padlet", "title": "Latest Padlet Changelog Entry", "content": content, "url": url, "status": status}
    except Exception as e:
        log_error(f"Padlet scrape failed: {e}")
    return None

def scrape_panopto():
    url = "https://community.panopto.com/categories/release-notes?sort=new"
    log_info(f"Scraping Panopto Forum: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        first_post_link = soup.select_one('.Title a, a.Title, .DiscussionName a, h3 a')
        if first_post_link:
            post_url = first_post_link['href']
            if not post_url.startswith("http"):
                post_url = "https://community.panopto.com" + post_url
            post_soup = get_soup(post_url)
            if post_soup:
                content = extract_content(post_soup, ['div.Message', 'div.Discussion', 'div.Item-Body'])
                return {"tool": "Panopto", "title": first_post_link.text.strip(), "content": content, "url": post_url}
    except Exception as e:
        log_error(f"Panopto scrape failed: {e}")
    return None

def scrape_playposit():
    url = "https://knowledge.playposit.com/article/85-release-notes"
    log_info(f"Scraping Playposit: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        content = extract_content(soup, ['section.article-body', 'div#article-body', 'article', 'div.content'])
        months_pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b'
        matches = list(re.finditer(months_pattern, content))
        if len(matches) >= 2:
            content = content[matches[0].start() : matches[1].start()]
        elif len(matches) == 1:
            content = content[matches[0].start() :]
        return {"tool": "PlayPosit", "title": "PlayPosit Latest Release", "content": content.strip(), "url": url}
    except Exception as e:
        log_error(f"Playposit scrape failed: {e}")
    return None

def scrape_readspeaker():
    url = "https://announcements.readspeaker.com/release-notes/feed/"
    log_info(f"Scraping ReadSpeaker (RSS): {url}")
    try:
        feed = feedparser.parse(url)
        if feed.entries:
            latest = feed.entries[0]
            clean_text = BeautifulSoup(latest.description, "html.parser").get_text(separator="\n").strip()
            return {"tool": "ReadSpeaker", "title": latest.title, "content": clean_text, "url": latest.link}
    except Exception as e:
        log_error(f"ReadSpeaker scrape failed: {e}")
    return None

def scrape_respondus():
    url = "https://support.respondus.com/hc/en-us/sections/4409696144411-Respondus-Announcements"
    log_info(f"Scraping Respondus (Zendesk Section): {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        first_article = soup.find('a', class_='article-list-link')
        if first_article:
            article_url = "https://support.respondus.com" + first_article['href']
            article_soup = get_soup(article_url)
            if article_soup:
                content = extract_content(article_soup, ['div.article-body'])
                return {"tool": "Respondus", "title": first_article.text.strip(), "content": content, "url": article_url}
    except Exception as e:
        log_error(f"Respondus scrape failed: {e}")
    return None

def scrape_simplesyllabus():
    url = "https://simplesyllabus.zendesk.com/hc/en-us/sections/360007834551-Release-Notes"
    log_info(f"Scraping Simple Syllabus: {url}")
    
    username = os.getenv("SS_USERNAME")
    password = os.getenv("SS_PASSWORD")
    
    # Use HTTP Basic Auth if credentials exist
    auth = (username, password) if username and password else None
    soup = get_soup(url, auth=auth)
    if not soup: return None
    
    try:
        first_article = soup.select_one(".article-list-item__link, a.article-list-link")
        if first_article:
            article_url = first_article.get("href")
            if not article_url.startswith("http"):
                article_url = "https://simplesyllabus.zendesk.com" + article_url
            
            art_soup = get_soup(article_url, auth=auth)
            if art_soup:
                content = extract_content(art_soup, ['.article-body', '.article__body', '.article-content'])
                return {"tool": "Simple Syllabus", "title": first_article.text.strip(), "content": content, "url": article_url}
    except Exception as e:
        log_error(f"Simple Syllabus scrape failed: {e}")
    return None

def scrape_turnitin():
    url = "https://guides.turnitin.com/hc/en-us/articles/27251688507533-Turnitin-release-notes"
    log_info(f"Scraping Turnitin (Direct): {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        body = soup.find('div', class_='article-body')
        if not body: return None
        full_text = body.get_text(separator="\n").strip()
        pattern = r'(202\d\s[A-Z][a-z]+\s\d{1,2}.*?)(?=\n\n|\n[A-Z][a-z]+\s202\d|\Z)'
        match = re.search(pattern, full_text, re.DOTALL)
        content = match.group(1).strip() if match else full_text
        return {"tool": "Turnitin", "title": "Latest Turnitin Release", "content": content, "url": url}
    except Exception as e:
        log_error(f"Turnitin scrape failed: {e}")
    return None

def scrape_qwickly():
    url = "https://www.goqwickly.com/installation/#releaseInfo"
    log_info(f"Scraping Qwickly: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        content = extract_content(soup, ["#releaseInfo", "main", "body"])
        matches = list(re.finditer(r'(Updates Applied \d{1,2}/\d{1,2}/\d{4})', content))
        if len(matches) >= 2:
            content = content[matches[0].start() : matches[1].start()]
        elif len(matches) == 1:
            content = content[matches[0].start() :]
        return {"tool": "Qwickly Course Tools", "title": "Qwickly Latest Update", "content": content.strip(), "url": url}
    except Exception as e:
        log_error(f"Qwickly scrape failed: {e}")
    return None

def scrape_zoom():
    url = "https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0080363"
    log_info(f"Scraping Zoom Table: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        table = soup.find("table")
        if not table: return None
        
        table_data = []
        for row in table.find_all("tr"):
            cols = [col.get_text(strip=True) for col in row.find_all(["td", "th"])]
            if cols: table_data.append(cols)
            
        return {
            "tool": "Zoom", 
            "title": "Zoom Release Notes Table", 
            "is_table": True, 
            "data": table_data, 
            "url": url
        }
    except Exception as e:
        log_error(f"Zoom scrape failed: {e}")
        return None

SCRAPE_FAILURE_MARKERS = (
    "ERR_HTTP2_PROTOCOL_ERROR",
    "This site can't be reached",
    "Content not found.",
    "Could not extract full pages.",
)


def _is_valid_scrape(item: dict) -> bool:
    """Filters out results that are really failed fetches (bot blocks, dead pages)
    instead of actual release-note content, so they never reach the Word doc / Gemini."""
    if item.get("is_table"):
        return bool(item.get("data"))
    content = item.get("content", "") or ""
    if not content.strip():
        return False
    return not any(marker in content for marker in SCRAPE_FAILURE_MARKERS)


def scrape_all():
    """Executes all scrapers and compiles the results."""
    results = []
    scrapers = [
        scrape_adobe, scrape_ally, scrape_canvas, scrape_equidox,
        scrape_gradescope, scrape_padlet, scrape_panopto, scrape_playposit,
        scrape_readspeaker, scrape_respondus, scrape_simplesyllabus,
        scrape_turnitin, scrape_qwickly, scrape_zoom
    ]

    for scraper in scrapers:
        try:
            result = scraper()
            if result and _is_valid_scrape(result):
                results.append(result)
                log_info(f"Successfully scraped {result['tool']}")
            elif result:
                log_warning(f"Discarded {result.get('tool', scraper.__name__)}: content looks like a failed fetch, not release notes.")
            else:
                log_warning(f"No valid data returned for {scraper.__name__}")
        except Exception as e:
            log_error(f"Critical error running {scraper.__name__}: {e}")
            
    return results