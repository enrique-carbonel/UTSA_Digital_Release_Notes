import requests
from bs4 import BeautifulSoup
import feedparser
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.logger import log_info, log_error, log_warning
import os

# --- Helper Functions ---

def get_soup(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        log_error(f"Failed to fetch HTML for {url}: {e}")
        return None

def setup_selenium():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=options)

def extract_content(soup, css_selectors):
    """Attempts to find content using specific selectors. Cleans out junk."""
    for selector in css_selectors:
        element = soup.select_one(selector)
        if element:
            # Strip out any embedded menus or sidebars inside the content
            for junk in element(["nav", "footer", "script", "style", "header", "aside"]):
                junk.decompose()
            # separator="\n" prevents words from mashing together
            return element.get_text(separator="\n").strip()
    
    # FOOLPROOF FALLBACK
    if soup.body:
        for junk in soup(["script", "style", "nav", "footer", "header", "aside"]):
            junk.decompose()
        return soup.body.get_text(separator="\n").strip()
        
    return "Content not found."

# --- Individual Scrapers ---

def scrape_adobe():
    url = "https://helpx.adobe.com/creative-cloud/apps/whats-new/release-notes.html"
    log_info(f"Scraping Adobe CC (Selenium): {url}")
    try:
        driver = setup_selenium()
        driver.get(url)
        time.sleep(4) # Let Adobe's heavy page load
        content = driver.find_element(By.TAG_NAME, "body").text
        driver.quit()
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
        
        # FIX: Find all version tags. Keep ONLY the text between the 1st and 2nd version tag.
        matches = list(re.finditer(r'(Ally\s\d+\.\d+\.\d+\s*Release to production:)', content))
        if len(matches) >= 2:
            # Cut from the 1st update down to where the 2nd update starts
            content = content[matches[0].start() : matches[1].start()]
        elif len(matches) == 1:
            content = content[matches[0].start() :]
            
        return {"tool": "Ally Accessibility Checker", "title": "Ally Latest Release", "content": content.strip(), "url": url}
    except Exception as e:
        log_error(f"Ally scrape failed: {e}")
    return None

def parse_html_with_tables(html_content):
    """Converts HTML content to text, ensuring tables are formatted cleanly into plain text."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Process tables first so they don't get mashed into a single paragraph
    for table in soup.find_all('table'):
        table_text = []
        for row in table.find_all('tr'):
            cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
            if cells:
                table_text.append(" | ".join(cells))
                
        # 2. Replace the HTML table element with our clean text version
        if table_text:
            new_text = soup.new_string("\n\n" + "\n".join(table_text) + "\n\n")
            table.replace_with(new_text)
            
    # 3. Get the rest of the text, separating paragraphs
    text = soup.get_text(separator="\n").strip()
    
    # Clean up excessive blank lines created by empty forum tags
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def scrape_canvas():
    index_url = "https://community.instructure.com/en/categories/canvas-release-notes"
    base_domain = "https://community.instructure.com"
    log_info(f"Scraping Canvas: Discovering latest links at {index_url}")
    
    try:
        driver = setup_selenium()
        driver.get(index_url)
        time.sleep(5) 
        
        # --- PHASE 1: DISCOVER URLS ---
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        release_url = None
        release_a = soup.find('a', class_='canvasRelease__featuredTitle', string=lambda text: text and "Canvas Release Notes (20" in text)
        if release_a and release_a.get('href'):
            href = release_a['href']
            release_url = href if href.startswith('http') else base_domain + href
            
        try:
            deploy_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Deploys')]")
            driver.execute_script("arguments[0].click();", deploy_tab)
            time.sleep(4)
        except Exception as e:
            log_error(f"Failed to click Deploys tab during discovery: {e}")
            
        soup_deploy = BeautifulSoup(driver.page_source, 'html.parser')
        deploy_url = None
        deploy_a = soup_deploy.find('a', class_='canvasRelease__featuredTitle', string=lambda text: text and "Canvas Deploy Notes (20" in text)
        if deploy_a and deploy_a.get('href'):
            href = deploy_a['href']
            deploy_url = href if href.startswith('http') else base_domain + href


        # --- PHASE 2: DEEP EXTRACTION (Bulletproofed) ---
        release_content = ""
        release_title = "Latest Release"
        
        # A cascading list of common article containers
        content_selectors = [
            ".lia-message-body-content", # Legacy Instructure
            ".Message-body",             # Modern forum body
            "article",                   # HTML5 article tag
            ".article-content",          # Generic CMS
            ".post-body",                # Blog style
            "[role='main']",             # Accessibility standard
            "main"                       # HTML5 main block
        ]
        
        if release_url:
            log_info(f"Navigating to deep Release URL: {release_url}")
            driver.get(release_url)
            time.sleep(6) 
            
            try:
                soup_deep = BeautifulSoup(driver.page_source, 'html.parser')
                body_element = None
                
                # Loop through our selectors until we find the content
                for selector in content_selectors:
                    body_element = soup_deep.select_one(selector)
                    if body_element:
                        break
                        
                # Ultimate fallback: just grab the whole body if nothing else works
                if not body_element:
                    body_element = soup_deep.body 
                    
                release_content = parse_html_with_tables(str(body_element))
                release_title = driver.title.split('-')[0].strip()
            except Exception as e:
                log_error(f"Could not extract body from release page: {e}")

        deploy_content = ""
        deploy_title = "Latest Deploy"
        
        if deploy_url:
            log_info(f"Navigating to deep Deploy URL: {deploy_url}")
            driver.get(deploy_url)
            time.sleep(6)
            
            try:
                soup_deep = BeautifulSoup(driver.page_source, 'html.parser')
                body_element = None
                
                for selector in content_selectors:
                    body_element = soup_deep.select_one(selector)
                    if body_element:
                        break
                        
                if not body_element:
                    body_element = soup_deep.body
                    
                deploy_content = parse_html_with_tables(str(body_element))
                deploy_title = driver.title.split('-')[0].strip()
            except Exception as e:
                log_error(f"Could not extract body from deploy page: {e}")

        driver.quit()
        
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
        try: driver.quit() 
        except: pass
        return None

def scrape_equidox():
    url = "https://www.app2.equidox.co/#/login"
    log_info(f"Scraping Equidox (Selenium): {url}")
    try:
        driver = setup_selenium()
        driver.get(url)
        time.sleep(5) 
        
        try:
            content = driver.find_element(By.CSS_SELECTOR, "div.release-notes, mat-dialog-content").text
        except:
            # Fallback: Grab body, but slice out the login form junk
            content = driver.find_element(By.TAG_NAME, "body").text
            if "Equidox" in content and "Live!" in content:
                content = content[content.find("Equidox"):] # Start reading from the word "Equidox"
                
        driver.quit()
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
        
        # Get full text, clean up extra spaces
        text = body.get_text(separator="\n").strip()
        
        # Slicing logic:
        # 1. We look for the first line that looks like a date (e.g., "2025 December 5th")
        # 2. We stop capturing as soon as we hit the second date header
        
        # Regex explanation:
        # It finds the first Date Header (e.g., 2025 December 5th)
        # Then it uses a 'lookahead' to stop at the next Month/Year header
        pattern = r'(202\d\s[A-Z][a-z]+\s\d{1,2}(?:st|nd|rd|th)?.*?)(?=\n\n|\n[A-Z][a-z]+\s202\d|\Z)'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            # We construct the content string manually to ensure zero 'trash' from other months
            # match.group(1) is the entire entry including the date and the paragraph
            content = match.group(1).strip()
            return {"tool": "Gradescope", "title": "Latest Gradescope Update", "content": content, "url": url}
            
        return {"tool": "Gradescope", "title": "Latest Gradescope Updates", "content": text, "url": url}
    except Exception as e:
        log_error(f"Gradescope scrape failed: {e}")
    return None

def scrape_padlet():
    url = "https://padlet.com/padlets/padlet-changelog-aft232zazwoplc0c"
    log_info(f"Scraping Padlet (Selenium): {url}")
    try:
        driver = setup_selenium()
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article, div.post-container, div[data-testid='post']")))
        cards = driver.find_elements(By.CSS_SELECTOR, "article, div.post-container, div[data-testid='post']")
        if cards:
            latest_card = cards[0]
            content = latest_card.text
            status = "Beta" if "beta" in content.lower() else "Released"
            driver.quit()
            return {"tool": "Padlet", "title": "Latest Padlet Changelog Entry", "content": content, "url": url, "status": status}
        driver.quit()
    except Exception as e:
        log_error(f"Padlet scrape failed: {e}")
    return None

def scrape_panopto():
    url = "https://community.panopto.com/categories/release-notes?sort=new"
    log_info(f"Scraping Panopto Forum: {url}")
    soup = get_soup(url)
    if not soup: return None
    try:
        # Broadened selectors for Vanilla Forums
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
        
        # FIX: Find all Month headers. Keep ONLY the text of the most recent month.
        months_pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b'
        matches = list(re.finditer(months_pattern, content))
        
        if len(matches) >= 2:
            content = content[matches[0].start() : matches[1].start()]
        elif len(matches) == 1:
            content = content[matches[0].start() :]
            
        return {"tool": "Playposit", "title": "Playposit Latest Release", "content": content.strip(), "url": url}
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
    log_info(f"Scraping Simple Syllabus (Selenium Login): {url}")
    
    username = os.getenv("SS_USERNAME")
    password = os.getenv("SS_PASSWORD")
    
    if not username or not password:
        log_error("Simple Syllabus credentials missing from .env file.")
        return None

    try:
        driver = setup_selenium()
        driver.get(url)
        time.sleep(5) 
        
        # --- PHASE 1: LOGIN ---
        try:
            email_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input#user_email")))
            email_field.send_keys(username)
            pass_field = driver.find_element(By.CSS_SELECTOR, "input[type='password'], input#user_password")
            pass_field.send_keys(password)
            submit_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit'], input[name='commit']")
            submit_btn.click()
        except Exception as e:
            driver.save_screenshot("simplesyllabus_error_1_login.png")
            log_error("Failed at login screen.")
            driver.quit()
            return None

        # --- PHASE 2: FIND LATEST ARTICLE ---
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "article-list-item__link")))
            first_article = driver.find_element(By.CLASS_NAME, "article-list-item__link")
            article_url = first_article.get_attribute("href")
            article_title = first_article.text
        except Exception as e:
            driver.save_screenshot("simplesyllabus_error_2_list.png")
            log_error("Login passed, but failed to find articles.")
            driver.quit()
            return None
        
        log_info(f"Diving into: {article_title}")
        driver.get(article_url)
        
# --- PHASE 3: THE "IMAGE SCISSORS" (BeautifulSoup Version) ---
        try:
            # Wait for the article body to render
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".article-body, .article__body, .article-content")))
            
            # Grab the HTML and close the browser
            html = driver.page_source
            driver.quit()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. Hunt down the exact image with "simple syllabus" in the alt text
            target_img = None
            for img in soup.find_all('img'):
                if 'simple syllabus' in img.get('alt', '').lower():
                    target_img = img
                    break
            
            if target_img:
                # 2. Find the main article container so we know where to stop climbing
                article_body = soup.select_one('.article-body, .article__body, .article-content, [itemprop="articleBody"]')
                if not article_body:
                    article_body = target_img.parent # Fallback
                    
                # Climb out of the image's wrapper (<figure> or <p>)
                current_node = target_img
                while current_node.parent and current_node.parent != article_body:
                    current_node = current_node.parent
                    
                content = []
                
                # 3. Read every element AFTER the wrapper
                for sibling in current_node.find_next_siblings():
                    
                    # Check if this sibling contains a DIFFERENT product logo
                    stop_capturing = False
                    images_in_sibling = sibling.find_all('img') if sibling.name != 'img' else [sibling]
                    
                    for img in images_in_sibling:
                        alt_text = img.get('alt', '').lower()
                        # If the image is a logo (like "Simple Prep logo") but NOT the Simple Syllabus logo, STOP!
                        if 'logo' in alt_text and 'simple syllabus' not in alt_text:
                            stop_capturing = True
                            break
                            
                    if stop_capturing:
                        break # Turn the camera OFF!
                        
                    # Extract the text and clean up Zendesk's invisible spaces
                    text = sibling.get_text(separator=" ").strip()
                    text = text.replace('\xa0', ' ').strip() 
                    
                    if text:
                        content.append(text)
                
                final_text = "\n".join(content)
                
                if final_text:
                    return {"tool": "Simple Syllabus", "title": article_title, "content": final_text, "url": article_url}
                else:
                    return {"tool": "Simple Syllabus", "title": article_title, "content": "Found the logo, but no text followed it.", "url": article_url}
            else:
                return {"tool": "Simple Syllabus", "title": article_title, "content": "Could not locate the Simple Syllabus logo.", "url": article_url}

        except Exception as e:
            log_error(f"Failed to parse article: {e}")
            try: driver.quit() 
            except: pass
            return None

    except Exception as e:
        log_error(f"Simple Syllabus scrape failed: {e}")
        try: driver.quit() 
        except: pass
        return None

def scrape_turnitin():
    # Direct link to the specific Turnitin Release Notes article page
    url = "https://guides.turnitin.com/hc/en-us/articles/27251688507533-Turnitin-release-notes"
    log_info(f"Scraping Turnitin (Direct): {url}")
    
    soup = get_soup(url)
    if not soup: return None
    
    try:
        # Get the main content block
        body = soup.find('div', class_='article-body')
        if not body: return None
        
        full_text = body.get_text(separator="\n").strip()
        
        # Regex explanation:
        # 1. Look for a date header like "2026 May 27"
        # 2. Capture the title and the following descriptive text
        # 3. Stop when we see another Month/Year or the end of the text
        pattern = r'(202\d\s[A-Z][a-z]+\s\d{1,2}.*?)(?=\n\n|\n[A-Z][a-z]+\s202\d|\Z)'
        match = re.search(pattern, full_text, re.DOTALL)
        
        if match:
            content = match.group(1).strip()
            return {"tool": "Turnitin", "title": "Latest Turnitin Release", "content": content, "url": url}
        
        # Fallback if no match found
        return {"tool": "Turnitin", "title": "Turnitin Release Notes", "content": "Could not extract latest release block.", "url": url}
        
    except Exception as e:
        log_error(f"Turnitin scrape failed: {e}")
        return None

def scrape_qwickly():
    url = "https://www.goqwickly.com/installation/#releaseInfo"
    log_info(f"Scraping Qwickly (Selenium): {url}")
    try:
        driver = setup_selenium()
        driver.get(url)
        time.sleep(4) 
        content = driver.find_element(By.TAG_NAME, "body").text
        
        # FIX: Find all "Updates Applied" blocks. Keep only the top one.
        matches = list(re.finditer(r'(Updates Applied \d{1,2}/\d{1,2}/\d{4})', content))
        if len(matches) >= 2:
            content = content[matches[0].start() : matches[1].start()]
        elif len(matches) == 1:
            content = content[matches[0].start() :]
            
        driver.quit()
        return {"tool": "Qwickly Course Tools", "title": "Qwickly Latest Update", "content": content.strip(), "url": url}
    except Exception as e:
        log_error(f"Qwickly scrape failed: {e}")
    return None

def scrape_zoom():
    url = "https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0080363"
    log_info(f"Scraping Zoom Table: {url}")
    try:
        driver = setup_selenium()
        driver.get(url)
        time.sleep(5) # Let the table render
        
        # Find the main table containing the release notes
        table = driver.find_element(By.TAG_NAME, "table")
        rows = table.find_elements(By.TAG_NAME, "tr")
        
        table_data = []
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if cols:
                # Extract text from each column
                table_data.append([col.text.strip() for col in cols])
        
        driver.quit()
        
        # Instead of just returning a string, we return the structured table list
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




def scrape_all():
    """Executes all scrapers and compiles the results."""
    results = []
    
    scrapers = [
        scrape_adobe,
        scrape_ally,
        scrape_canvas,
        scrape_equidox,
        scrape_gradescope,
        scrape_padlet,
        scrape_panopto,
        scrape_playposit,
        scrape_readspeaker,
        scrape_respondus,
        scrape_simplesyllabus,
        scrape_turnitin,
        scrape_qwickly,
        scrape_zoom
    ]
    
    for scraper in scrapers:
        try:
            result = scraper()
            if result:
                results.append(result)
                log_info(f"Successfully scraped {result['tool']}")
            else:
                log_warning(f"No valid data returned for {scraper.__name__}")
        except Exception as e:
            log_error(f"Critical error running {scraper.__name__}: {e}")
            
    return results