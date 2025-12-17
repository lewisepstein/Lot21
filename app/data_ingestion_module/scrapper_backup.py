"""
Web scraping module for extracting content from web pages.
Uses BeautifulSoup and requests for HTML parsing and HTTP requests.
"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scrape_webpage(
    url: str,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    parse_images: bool = True,
    parse_links: bool = True,
    parse_meta: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Scrape a webpage and extract its content using BeautifulSoup.
    
    Args:
        url (str): The URL of the webpage to scrape
        timeout (int): Request timeout in seconds (default: 30)
        headers (dict): Optional custom headers for the request
        parse_images (bool): Whether to extract image URLs (default: True)
        parse_links (bool): Whether to extract all links (default: True)
        parse_meta (bool): Whether to extract meta tags (default: True)
        
    Returns:
        dict: Dictionary containing scraped data with keys:
            - url: The scraped URL
            - title: Page title
            - text: Extracted text content
            - html: Raw HTML content
            - images: List of image URLs (if parse_images=True)
            - links: List of links (if parse_links=True)
            - meta: Dictionary of meta tags (if parse_meta=True)
            - headings: Dictionary of headings (h1, h2, h3, etc.)
            - paragraphs: List of paragraph texts
        None if scraping fails
    """
    try:
        # Set default headers if not provided
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        # Make the HTTP request
        logger.info(f"Scraping URL: {url}")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Initialize result dictionary
        result = {
            'url': url,
            'status_code': response.status_code,
            'title': None,
            'text': None,
            'html': response.text,
            'images': [],
            'links': [],
            'meta': {},
            'headings': {},
            'paragraphs': []
        }
        
        # Extract title
        title_tag = soup.find('title')
        result['title'] = title_tag.get_text(strip=True) if title_tag else None
        
        # Extract text content (remove script and style elements)
        for script in soup(['script', 'style', 'noscript']):
            script.decompose()
        result['text'] = soup.get_text(separator=' ', strip=True)
        
        # Extract images
        if parse_images:
            images = []
            for img in soup.find_all('img'):
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(url, img_url)
                    images.append({
                        'url': absolute_url,
                        'alt': img.get('alt', ''),
                        'title': img.get('title', '')
                    })
            result['images'] = images
            logger.info(f"Found {len(images)} images")
        
        # Extract links
        if parse_links:
            links = []
            for link in soup.find_all('a', href=True):
                link_url = link['href']
                absolute_url = urljoin(url, link_url)
                links.append({
                    'url': absolute_url,
                    'text': link.get_text(strip=True),
                    'title': link.get('title', '')
                })
            result['links'] = links
            logger.info(f"Found {len(links)} links")
        
        # Extract meta tags
        if parse_meta:
            meta_tags = {}
            for meta in soup.find_all('meta'):
                name = meta.get('name') or meta.get('property')
                content = meta.get('content')
                if name and content:
                    meta_tags[name] = content
            result['meta'] = meta_tags
            logger.info(f"Found {len(meta_tags)} meta tags")
        
        # Extract headings
        headings = {}
        for i in range(1, 7):  # h1 to h6
            h_tags = soup.find_all(f'h{i}')
            if h_tags:
                headings[f'h{i}'] = [h.get_text(strip=True) for h in h_tags]
        result['headings'] = headings
        
        # Extract paragraphs
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
        result['paragraphs'] = paragraphs
        logger.info(f"Found {len(paragraphs)} paragraphs")
        
        logger.info(f"Successfully scraped: {url}")
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error while scraping {url}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while scraping {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error scraping webpage {url}: {e}", exc_info=True)
        return None


def scrape_multiple_pages(
    urls: List[str],
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    parse_images: bool = True,
    parse_links: bool = True,
    parse_meta: bool = True
) -> List[Dict[str, Any]]:
    """
    Scrape multiple webpages.
    
    Args:
        urls (list): List of URLs to scrape
        timeout (int): Request timeout in seconds (default: 30)
        headers (dict): Optional custom headers for the request
        parse_images (bool): Whether to extract image URLs (default: True)
        parse_links (bool): Whether to extract all links (default: True)
        parse_meta (bool): Whether to extract meta tags (default: True)
        
    Returns:
        list: List of dictionaries containing scraped data for each URL
    """
    results = []
    
    logger.info(f"Starting to scrape {len(urls)} pages")
    
    for url in urls:
        result = scrape_webpage(
            url=url,
            timeout=timeout,
            headers=headers,
            parse_images=parse_images,
            parse_links=parse_links,
            parse_meta=parse_meta
        )
        
        if result:
            results.append(result)
    
    logger.info(f"Successfully scraped {len(results)} out of {len(urls)} pages")
    return results


def extract_specific_elements(
    url: str,
    css_selectors: Dict[str, str],
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Scrape specific elements from a webpage using CSS selectors.
    
    Args:
        url (str): The URL of the webpage to scrape
        css_selectors (dict): Dictionary mapping field names to CSS selectors
                             Example: {'title': 'h1.main-title', 'price': 'span.price'}
        timeout (int): Request timeout in seconds (default: 30)
        headers (dict): Optional custom headers for the request
        
    Returns:
        dict: Dictionary containing extracted elements mapped to their values
        None if scraping fails
    """
    try:
        # Set default headers if not provided
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        # Make the HTTP request
        logger.info(f"Scraping specific elements from: {url}")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract elements based on CSS selectors
        result = {'url': url}
        
        for field_name, selector in css_selectors.items():
            elements = soup.select(selector)
            
            if len(elements) == 1:
                # Single element - return text directly
                result[field_name] = elements[0].get_text(strip=True)
            elif len(elements) > 1:
                # Multiple elements - return as list
                result[field_name] = [elem.get_text(strip=True) for elem in elements]
            else:
                # No elements found
                result[field_name] = None
            
            logger.info(f"Extracted {field_name}: {len(elements)} element(s) found")
        
        return result
        
    except Exception as e:
        logger.error(f"Error extracting specific elements from {url}: {e}", exc_info=True)
        return None


def scrape_container_content(
    url: str,
    container_selector: str = 'main#primary div.container',
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    extract_html: bool = True,
    extract_text: bool = True,
    extract_links: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Scrape content from a specific container element on a webpage.
    Useful for extracting content from main content areas, specific divs, etc.
    
    Args:
        url (str): The URL of the webpage to scrape
        container_selector (str): CSS selector for the container element
                                 Default: 'main#primary div.container'
        timeout (int): Request timeout in seconds (default: 30)
        headers (dict): Optional custom headers for the request
        extract_html (bool): Whether to extract raw HTML of the container (default: True)
        extract_text (bool): Whether to extract text content (default: True)
        extract_links (bool): Whether to extract links within container (default: True)
        
    Returns:
        dict: Dictionary containing:
            - url: The scraped URL
            - container_found: Boolean indicating if container was found
            - html: Raw HTML of the container (if extract_html=True)
            - text: Cleaned text content (if extract_text=True)
            - links: List of link data (if extract_links=True)
            - headings: Dictionary of headings within container
            - paragraphs: List of paragraphs within container
        None if scraping fails
    """
    try:
        # Set default headers if not provided
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        # Make the HTTP request
        logger.info(f"Scraping container content from: {url}")
        logger.info(f"Using selector: {container_selector}")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the container element
        container = soup.select_one(container_selector)
        
        result = {
            'url': url,
            'container_selector': container_selector,
            'container_found': container is not None
        }
        
        if not container:
            logger.warning(f"Container not found with selector: {container_selector}")
            return result
        
        logger.info(f"Container found with selector: {container_selector}")
        
        # Extract raw HTML of the container
        if extract_html:
            result['html'] = str(container)
        
        # Extract text content
        if extract_text:
            # Remove script and style elements
            for script in container.find_all(['script', 'style', 'noscript']):
                script.decompose()
            result['text'] = container.get_text(separator=' ', strip=True)
        
        # Extract links within container
        if extract_links:
            links = []
            for link in container.find_all('a', href=True):
                link_url = link['href']
                absolute_url = urljoin(url, link_url)
                links.append({
                    'url': absolute_url,
                    'text': link.get_text(strip=True),
                    'title': link.get('title', ''),
                    'class': link.get('class', [])
                })
            result['links'] = links
            logger.info(f"Found {len(links)} links in container")
        
        # Extract headings within container
        headings = {}
        for i in range(1, 7):  # h1 to h6
            h_tags = container.find_all(f'h{i}')
            if h_tags:
                headings[f'h{i}'] = [h.get_text(strip=True) for h in h_tags]
        result['headings'] = headings
        
        # Extract paragraphs within container
        paragraphs = [p.get_text(strip=True) for p in container.find_all('p') if p.get_text(strip=True)]
        result['paragraphs'] = paragraphs
        logger.info(f"Found {len(paragraphs)} paragraphs in container")
        
        logger.info(f"Successfully scraped container content from: {url}")
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error while scraping {url}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while scraping {url}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error scraping container content from {url}: {e}", exc_info=True)
        return None


    except Exception as e:
        logger.error(f"Error scraping container content from {url}: {e}", exc_info=True)
        return None


def scrape_page_sections(
    url: str,
    section_selectors: Dict[str, str],
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
    split_by_headings: bool = True
) -> List[Dict[str, Any]]:
    """
    Scrape multiple sections from a webpage and return in structured format.
    Each heading tag creates a new entry in the returned list.
    
    Args:
        url (str): The URL of the webpage to scrape
        section_selectors (dict): Dictionary mapping section names to CSS selectors
                                 Example: {'main': 'main#primary div.container',
                                          'column1': 'div.column-1'}
        timeout (int): Request timeout in seconds (default: 30)
        headers (dict): Optional custom headers for the request
        split_by_headings (bool): If True, create separate entries for each heading (default: True)
        
    Returns:
        list: List of dictionaries, each containing:
            - pageTitle: The page title
            - slug: URL slug (last part of path)
            - sourceUrl: The full source URL
            - section: Section name
            - heading: The heading text (if split_by_headings=True)
            - headingLevel: The heading level (h1, h2, etc.)
            - content: Text content from the section/subsection
            - url: First URL found in section (if any)
            - url_1, url_2, etc.: Additional URLs if multiple found
    """
    try:
        # Set default headers if not provided
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        # Make the HTTP request
        logger.info(f"Scraping page sections from: {url}")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract page title
        title_tag = soup.find('title')
        page_title = title_tag.get_text(strip=True) if title_tag else None
        
        # Extract slug from URL (last part of path)
        parsed_url = urlparse(url)
        path_parts = [p for p in parsed_url.path.split('/') if p]
        slug = path_parts[-1] if path_parts else None
        
        # Process each section
        sections_data = []
        
        for section_name, selector in section_selectors.items():
            section_element = soup.select_one(selector)
            
            if section_element:
                logger.info(f"Found section '{section_name}' with selector: {selector}")
                
                if split_by_headings:
                    # Find all heading tags in this section
                    headings = section_element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    
                    if headings:
                        # Process each heading and its content
                        for i, heading in enumerate(headings):
                            heading_text = heading.get_text(strip=True)
                            heading_level = heading.name
                            
                            # Get content after this heading until next heading
                            content_elements = []
                            for sibling in heading.next_siblings:
                                # Stop if we hit another heading at same or higher level
                                if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                    break
                                if hasattr(sibling, 'get_text'):
                                    text = sibling.get_text(separator=' ', strip=True)
                                    if text:
                                        content_elements.append(text)
                            
                            content = ' '.join(content_elements)
                            
                            # Extract URLs in this subsection
                            # Get all elements between this heading and next
                            subsection_elements = [heading]
                            for sibling in heading.next_siblings:
                                if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                    break
                                if hasattr(sibling, 'name'):
                                    subsection_elements.append(sibling)
                            
                            # Extract links from these elements
                            urls = []
                            for elem in subsection_elements:
                                if hasattr(elem, 'find_all'):
                                    links = elem.find_all('a', href=True)
                                    for link in links:
                                        link_url = link['href']
                                        absolute_url = urljoin(url, link_url)
                                        urls.append(absolute_url)
                            
                            # Build section dictionary
                            section_dict = {
                                "pageTitle": page_title,
                                "slug": slug,
                                "sourceUrl": url,
                                "section": section_name,
                                "heading": heading_text,
                                "headingLevel": heading_level,
                                "content": content
                            }
                            
                            # Add URLs
                            if len(urls) == 1:
                                section_dict["url"] = urls[0]
                            elif len(urls) > 1:
                                for j, link_url in enumerate(urls, start=1):
                                    section_dict[f"url_{j}"] = link_url
                            
                            sections_data.append(section_dict)
                            logger.info(f"Section '{section_name}', heading '{heading_text}': {len(urls)} URLs found")
                    else:
                        # No headings found, treat entire section as one entry
                        for script in section_element.find_all(['script', 'style', 'noscript']):
                            script.decompose()
                        
                        content = section_element.get_text(separator=' ', strip=True)
                        
                        links = section_element.find_all('a', href=True)
                        urls = []
                        for link in links:
                            link_url = link['href']
                            absolute_url = urljoin(url, link_url)
                            urls.append(absolute_url)
                        
                        section_dict = {
                            "pageTitle": page_title,
                            "slug": slug,
                            "sourceUrl": url,
                            "section": section_name,
                            "content": content
                        }
                        
                        if len(urls) == 1:
                            section_dict["url"] = urls[0]
                        elif len(urls) > 1:
                            for j, link_url in enumerate(urls, start=1):
                                section_dict[f"url_{j}"] = link_url
                        
                        sections_data.append(section_dict)
                        logger.info(f"Section '{section_name}': {len(urls)} URLs found (no headings)")
                else:
                    # Original behavior: treat entire section as one entry
                    for script in section_element.find_all(['script', 'style', 'noscript']):
                        script.decompose()
                    
                    content = section_element.get_text(separator=' ', strip=True)
                    
                    links = section_element.find_all('a', href=True)
                    urls = []
                    for link in links:
                        link_url = link['href']
                        absolute_url = urljoin(url, link_url)
                        urls.append(absolute_url)
                    
                    section_dict = {
                        "pageTitle": page_title,
                        "slug": slug,
                        "sourceUrl": url,
                        "section": section_name,
                        "content": content
                    }
                    
                    if len(urls) == 1:
                        section_dict["url"] = urls[0]
                    elif len(urls) > 1:
                        for j, link_url in enumerate(urls, start=1):
                            section_dict[f"url_{j}"] = link_url
                    
                    sections_data.append(section_dict)
                    logger.info(f"Section '{section_name}': {len(urls)} URLs found")
            else:
                logger.warning(f"Section '{section_name}' not found with selector: {selector}")
        
        logger.info(f"Successfully scraped {len(sections_data)} entries from {url}")
        return sections_data
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error while scraping {url}", exc_info=True)
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while scraping {url}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error scraping page sections from {url}: {e}", exc_info=True)
        return []
