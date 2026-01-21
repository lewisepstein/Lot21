import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from typing import Dict, Any
from service_utils.log_management import get_logger
from service_utils.helpers import validate_url
from collections import defaultdict

# Set up logging
logger = get_logger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}


TIMEOUT = 30  # seconds
TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "span", "li", "blockquote", "pre", "code"}

EXCLUDE_TEXT = {"attributions", "go deeper", "watch", "subscribe"}

def get_main_container(soup: BeautifulSoup):
    # WordPress (highest priority)
    for selector in [
        "div.entry-content",
        "div.page-content",
        "div.content-area",
        "div.site-content"
    ]:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el

    # Semantic HTML
    for selector in ["article", "main", "[role=main]"]:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el
        
    # Largest text-heavy div
    candidates = [
        d for d in soup.find_all("div")
        if len(d.get_text(strip=True)) > 200
    ]
    if candidates:
        return max(candidates, key=lambda d: len(d.get_text(strip=True)))

    # Fallbacks
    return soup.body or soup

def scrape_page(url: str):
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    main = get_main_container(soup)

    if not main:
        logger.warning("No main container found, using full document")
        main = soup

    blocks = []
    seen = set()
    order = 0

    for node in main.descendants:
        if not isinstance(node, Tag):
            continue

        if node.name not in TEXT_TAGS:
            continue

        text = node.get_text(strip=True)

        # Skip empty or very short noise
        if not text or len(text) < 5:
            continue

        # Deduplicate repeated CMS artifacts
        if text in seen:
            continue
        seen.add(text)

        blocks.append({
            "tag": node.name,
            "text": text,
            "order": order
        })
        order += 1

    title = soup.title.string.strip() if soup.title else None

    full_text = "\n\n".join(
        block["text"] for block in blocks if block["text"]
    )

    logger.info(f"Extracted {len(blocks)} text blocks")

    return {
        "title": title,
        "blocks": blocks,
        "content": full_text   
    }

def convert_to_wysiwyg_html(scraped_data: Dict[str, Any]) -> str:
    """
    Convert scraped data to WYSIWYG HTML format.
    
    Creates a complete HTML document with all headings, paragraphs, and lists
    properly formatted in a single WYSIWYG-ready format.
    
    Args:
        scraped_data: Dictionary returned from scrape_page() function with:
            - title: Page title
            - headings_with_content: List of heading sections with content
            
    Returns:
        String containing complete HTML formatted content
    """
    html_parts = []
    
    # Add each heading section with its content
    headings_with_content = scraped_data.get("headings_with_content", [])
    
    for section in headings_with_content:
        heading_text = section.get("heading", "")
        heading_level = section.get("heading_level", "h2")
        paragraphs = section.get("paragraphs", [])
        links = section.get("links", [])
        lists = section.get("lists", [])
        
        # Add heading
        if heading_text:
            html_parts.append(f"<{heading_level}>{heading_text}</{heading_level}>")
        
        # Add paragraphs
        for para in paragraphs:
            html_parts.append(f"<p>{para}</p>")
        
        # Add lists
        for list_items in lists:
            html_parts.append("<ul>")
            for item in list_items:
                html_parts.append(f"  <li>{item}</li>")
            html_parts.append("</ul>")
        
        # Add standalone links (not already in paragraphs/lists)
        if links:
            # Group standalone links that aren't embedded in paragraphs
            standalone_links = []
            for link in links:
                link_text = link.get('text', '')
                link_href = link.get('href', '')
                # Check if this link text appears in any paragraph
                is_in_paragraph = any(link_text in para for para in paragraphs)
                if not is_in_paragraph and link_text and link_href:
                    standalone_links.append(link)
            
            # Add standalone links as a paragraph with links
            if standalone_links:
                link_html = []
                for link in standalone_links:
                    link_html.append(f'<a href="{link["href"]}">{link["text"]}</a>')
                html_parts.append(f"<p>{' | '.join(link_html)}</p>")
    
    # Join all parts with newlines for readability
    return "\n".join(html_parts)

def scrape_content_from_url(source_url: str) -> str:
    """
    Scrape content from a URL and convert to WYSIWYG HTML.
    
    Args:
        source_url: URL to scrape content from
        
    Returns:
        Scraped HTML content in WYSIWYG format
        
    Raises:
        ValueError: If URL is invalid or scraping fails
    """
    if not source_url:
        raise ValueError("Source URL is required for scraping")
    
    # Validate URL format
    if not validate_url(source_url):
        raise ValueError("Invalid URL format. Please provide a valid HTTP or HTTPS URL")
    
    try:
        logger.info(f"Scraping content from URL: {source_url}")
        scraped_data = scrape_page(source_url)
        scraped_html = convert_to_wysiwyg_html(scraped_data)
        logger.info(f"Scraped HTML Content length: {len(scraped_html)} characters")
        logger.info(f"Successfully scraped content from {source_url}")
        return scraped_html
    except Exception as scrape_error:
        logger.error(f"Failed to scrape content from {source_url}: {scrape_error}")
        raise ValueError(f"Failed to scrape content from URL: {str(scrape_error)}")

