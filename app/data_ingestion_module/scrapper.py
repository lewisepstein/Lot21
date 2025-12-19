import requests
from bs4 import BeautifulSoup
from typing import Dict, Any
from service_utils.log_management import get_logger
from service_utils.helpers import validate_url

# Set up logging
logger = get_logger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

TIMEOUT = 30  # seconds

TAGS_TO_FIND = ["h1", "h2", "h3"]

# Headings to exclude along with their following content
EXCLUDE_HEADINGS = ["Attributions", "Go Deeper", "Watch", "Subscribe"]

def scrape_page(url):
    try:
        
        # Send HTTP GET request with headers
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()  # Raises error if request failed
        
        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = soup.title.string if soup.title else None
        
        # Extract headings with their following paragraphs and links
        headings_with_content = []
        
        for heading in soup.find_all(TAGS_TO_FIND):
            heading_text = heading.get_text(strip=True)
            
            # Skip headings that match the exclusion list
            if heading_text in EXCLUDE_HEADINGS:
                logger.info(f"Excluding heading and its content: {heading_text}")
                continue
            
            # Get all paragraphs, links, and lists that follow this heading until the next heading
            paragraphs = []
            links = []
            lists = []
            
            for sibling in heading.next_siblings:
                # Stop if we hit another heading
                if sibling.name in TAGS_TO_FIND:
                    break
                
                # Collect paragraph text (direct siblings)
                if sibling.name == 'p':
                    para_text = sibling.get_text(strip=True)
                    if para_text:
                        paragraphs.append(para_text)
                
                # Collect unordered lists
                elif sibling.name == 'ul':
                    list_items = []
                    for li in sibling.find_all('li'):
                        list_items.append(li.get_text(strip=True))
                    if list_items:
                        lists.append(list_items)
                            
                # Also fetch all links and nested paragraphs in other elements (divs, spans, etc.)
                elif hasattr(sibling, 'find_all'):
                    # Find paragraphs nested within other elements (not direct siblings)
                    for p in sibling.find_all('p'):
                        para_text = p.get_text(strip=True)
                        if para_text:
                            paragraphs.append(para_text)
                            
            # Only add the heading if it has at least one paragraph, link, or list
            if len(paragraphs) > 0 or len(lists) > 0:
                headings_with_content.append({
                    'heading': heading_text,
                    'heading_level': heading.name,
                    'paragraphs': paragraphs,
                    'links': links,
                    'lists': lists
                })
        
        result = {
            "title": title,
            "headings_with_content": headings_with_content
        }
        
        logger.info(f"Successfully scraped {url}: {len(headings_with_content)} sections found")
        return result
        
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {str(e)}")
        raise

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

