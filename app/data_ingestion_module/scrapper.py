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

# Tags to remove entirely before extraction (noise elements)
REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg", "form"}

# CSS selectors for common noise elements to remove
REMOVE_SELECTORS = [
    "nav", "footer", "header", ".sidebar", ".nav", ".menu", ".footer",
    ".header", ".advertisement", ".ads", ".ad", ".social-share",
    ".comments", "#comments", ".cookie-banner", ".popup", ".modal",
    "[role=navigation]", "[role=banner]", "[role=contentinfo]"
]


def get_main_container(soup: BeautifulSoup):
    """Find the main content container of the page."""
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

    # Common content div patterns
    for selector in [
        "div.content", "div.post-content", "div.article-content",
        "div.body-content", "div.main-content", "#content", "#main"
    ]:
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


def _clean_soup(soup: BeautifulSoup):
    """Remove noise elements from the soup before extraction."""
    # Remove script, style, nav, footer etc.
    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove common noise selectors
    for selector in REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()


def _extract_table(table_tag: Tag) -> str:
    """Extract table content as readable text."""
    rows = []
    for tr in table_tag.find_all("tr"):
        cells = []
        for cell in tr.find_all(["th", "td"]):
            cell_text = cell.get_text(strip=True)
            cells.append(cell_text)
        if cells:
            rows.append(" | ".join(cells))

    if rows:
        return "\n".join(rows)
    return ""


def _extract_list(list_tag: Tag) -> str:
    """Extract ordered/unordered list as readable text."""
    items = []
    is_ordered = list_tag.name == "ol"
    for i, li in enumerate(list_tag.find_all("li", recursive=False)):
        text = li.get_text(strip=True)
        if text:
            prefix = f"{i + 1}." if is_ordered else "-"
            items.append(f"{prefix} {text}")
    return "\n".join(items)


def _extract_definition_list(dl_tag: Tag) -> str:
    """Extract definition list as readable text."""
    parts = []
    for child in dl_tag.children:
        if isinstance(child, Tag):
            text = child.get_text(strip=True)
            if child.name == "dt" and text:
                parts.append(f"{text}:")
            elif child.name == "dd" and text:
                parts.append(f"  {text}")
    return "\n".join(parts)


def scrape_page(url: str):
    """
    Scrape complete content from a web page.

    Extracts all text content including headings, paragraphs, tables,
    lists, links, blockquotes, and code blocks.

    Args:
        url: The URL to scrape

    Returns:
        Dictionary with title, blocks, and full content text
    """
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Clean noise elements first
    _clean_soup(soup)

    main = get_main_container(soup)

    if not main:
        logger.warning("No main container found, using full document")
        main = soup

    blocks = []
    seen = set()
    order = 0
    processed_elements = set()

    def add_block(tag_name, text):
        """Helper to add a text block, handling deduplication."""
        nonlocal order
        if not text or text in seen:
            return
        seen.add(text)
        blocks.append({
            "tag": tag_name,
            "text": text,
            "order": order
        })
        order += 1

    for node in main.descendants:
        if not isinstance(node, Tag):
            continue

        # Skip if this element was already processed as part of a parent structure
        if id(node) in processed_elements:
            continue

        tag = node.name

        # Handle tables as a whole unit
        if tag == "table":
            table_text = _extract_table(node)
            if table_text:
                add_block("table", table_text)
            # Mark all children as processed
            for child in node.descendants:
                if isinstance(child, Tag):
                    processed_elements.add(id(child))
            continue

        # Handle ordered/unordered lists as a whole unit
        if tag in ("ul", "ol"):
            list_text = _extract_list(node)
            if list_text:
                add_block(tag, list_text)
            for child in node.descendants:
                if isinstance(child, Tag):
                    processed_elements.add(id(child))
            continue

        # Handle definition lists
        if tag == "dl":
            dl_text = _extract_definition_list(node)
            if dl_text:
                add_block("dl", dl_text)
            for child in node.descendants:
                if isinstance(child, Tag):
                    processed_elements.add(id(child))
            continue

        # Handle headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = node.get_text(strip=True)
            if text:
                add_block(tag, text)
            continue

        # Handle paragraphs - include link URLs inline
        if tag == "p":
            text = _extract_paragraph_with_links(node)
            if text and len(text) >= 3:
                add_block("p", text)
            continue

        # Handle blockquotes
        if tag == "blockquote":
            text = node.get_text(strip=True)
            if text:
                add_block("blockquote", text)
            for child in node.descendants:
                if isinstance(child, Tag):
                    processed_elements.add(id(child))
            continue

        # Handle preformatted text / code blocks
        if tag in ("pre", "code"):
            text = node.get_text(strip=True)
            if text:
                add_block(tag, text)
            for child in node.descendants:
                if isinstance(child, Tag):
                    processed_elements.add(id(child))
            continue

        # Handle figure captions
        if tag == "figcaption":
            text = node.get_text(strip=True)
            if text:
                add_block("figcaption", text)
            continue

    title = soup.title.string.strip() if soup.title and soup.title.string else None

    full_text = "\n\n".join(
        block["text"] for block in blocks if block["text"]
    )

    logger.info(f"Extracted {len(blocks)} content blocks, {len(full_text)} characters")

    return {
        "title": title,
        "blocks": blocks,
        "content": full_text
    }


def _extract_paragraph_with_links(p_tag: Tag) -> str:
    """
    Extract paragraph text, appending link URLs for important links.
    e.g., 'Visit our website (https://example.com) for more info.'
    """
    parts = []
    for child in p_tag.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(text)
        elif isinstance(child, Tag):
            if child.name == "a":
                link_text = child.get_text(strip=True)
                href = child.get("href", "")
                if link_text and href and href.startswith("http"):
                    parts.append(f"{link_text} ({href})")
                elif link_text:
                    parts.append(link_text)
            else:
                text = child.get_text(strip=True)
                if text:
                    parts.append(text)
    return " ".join(parts)


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
