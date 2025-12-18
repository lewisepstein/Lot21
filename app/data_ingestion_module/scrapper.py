import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from weaviate_module.weaviate_utils import (
    load_scraped_data_to_weaviate
)
from service_utils.log_management import get_logger

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

def scrape_page(url):
       
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
                # Also collect links within this paragraph
                for a in sibling.find_all('a', href=True):
                    links.append({
                        'text': a.get_text(strip=True),
                        'href': a['href']
                    })
            
            # Collect unordered lists
            elif sibling.name == 'ul':
                list_items = []
                for li in sibling.find_all('li'):
                    list_items.append(li.get_text(strip=True))
                if list_items:
                    lists.append(list_items)
                # Also collect links within the list
                for a in sibling.find_all('a', href=True):
                    links.append({
                        'text': a.get_text(strip=True),
                        'href': a['href']
                    })
            
            # Collect direct anchor tags (not inside paragraphs)
            elif sibling.name == 'a' and sibling.get('href'):
                links.append({
                    'text': sibling.get_text(strip=True),
                    'href': sibling['href']
                })
            
            # Also fetch all links and nested paragraphs in other elements (divs, spans, etc.)
            elif hasattr(sibling, 'find_all'):
                # Find paragraphs nested within other elements (not direct siblings)
                for p in sibling.find_all('p'):
                    para_text = p.get_text(strip=True)
                    if para_text:
                        paragraphs.append(para_text)
                
                # Find links in other elements
                for a in sibling.find_all('a', href=True):
                    links.append({
                        'text': a.get_text(strip=True),
                        'href': a['href']
                    })
        
        # Only add the heading if it has at least one paragraph, link, or list
        if len(paragraphs) > 0 or len(links) > 0 or len(lists) > 0:
            headings_with_content.append({
                'heading': heading_text,
                'heading_level': heading.name,
                'paragraphs': paragraphs,
                'links': links,
                'lists': lists
            })

    return {
        "title": title,
        "headings_with_content": headings_with_content
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
        
    Examples:
        >>> data = scrape_page(url)
        >>> html = convert_to_wysiwyg_html(data)
        >>> with open('output.html', 'w') as f:
        ...     f.write(html)
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


def insert_scraped_data_to_weaviate(
    scraped_data: Dict[str, Any],
    url: str,
    collection_name: str = "training_data",
    doc_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Insert scraped web page data into Weaviate collection.
    
    Converts scraped data to HTML and loads it as a single document.
    
    Args:
        scraped_data: Dictionary returned from scrape_page() function with:
            - title: Page title
            - headings_with_content: List of heading sections with content
        url: Source URL of the scraped page
        collection_name: Name of the Weaviate collection (default: "training_data")
        doc_id: Unique document identifier (default: uses URL)
        
    Returns:
        Dictionary with:
            - success: Boolean indicating success
            - collection_name: Name of the collection
            - chunks_created: Number of chunks inserted
            - doc_id: Document identifier used
            - source_url: Source URL
            
    Raises:
        RuntimeError: If Weaviate operations fail
        
    Examples:
        >>> url = "https://example.com/page"
        >>> data = scrape_page(url)
        >>> result = insert_scraped_data_to_weaviate(data, url)
        >>> print(f"Inserted {result['chunks_created']} chunks")
    """
    try:
        # Convert scraped data to WYSIWYG HTML
        html_content = convert_to_wysiwyg_html(scraped_data)
        
        # Use URL as doc_id if not provided
        if not doc_id:
            doc_id = url
        
        # Load to Weaviate using the helper function
        result = load_scraped_data_to_weaviate(
            scraped_content=html_content,
            collection_name=collection_name,
            source_url=doc_id,
            description=f"Scraped content from {url}"
        )
        
        logger.info(f"Successfully loaded scraped data from {url} - {result['chunks_created']} chunks created")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to insert scraped data to Weaviate: {str(e)}")
        raise RuntimeError(f"Failed to insert scraped data to Weaviate: {str(e)}")



# Example usage:
if __name__ == "__main__":
    url = "https://lot21.24livehost.com/discover/solutions/understanding/forest-carbon-practices/"
    
    # Scrape the page
    print(f"Scraping URL: {url}")
    data = scrape_page(url)

    print("Page Title:", data["title"])
    print("\n" + "="*80)
    print("SCRAPED DATA")
    print("="*80)
    print(f"Found {len(data['headings_with_content'])} sections")
    
    # Convert to WYSIWYG HTML
    print("\n" + "="*80)
    print("CONVERTING TO WYSIWYG HTML")
    print("="*80)
    
    html_content = convert_to_wysiwyg_html(data)
    print(html_content)
    
    # Save to file
    output_file = "scraped_content.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\n✓ HTML content saved to {output_file}")
    
    # Insert into Weaviate
    print("\n" + "="*80)
    print("INSERTING INTO WEAVIATE")
    print("="*80)
    
    try:
        result = insert_scraped_data_to_weaviate(
            scraped_data=data,
            url=url,
        )
        
        print("✓ Success!")
        print(f"  Collection: {result['collection_name']}")
        print(f"  Headings processed: {result['headings_processed']}")
        print(f"  Total chunks created: {result['total_chunks_created']}")
        print(f"  Document ID: {result['doc_id']}")
    except Exception as e:
        print(f"✗ Error inserting to Weaviate: {e}")