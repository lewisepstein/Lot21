import logging
from typing import Dict, List, Any, Optional
import requests

# Set up logging
logger = logging.getLogger(__name__)


def fetch_wordpress_graphql(
    graphql_endpoint: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch data from WordPress GraphQL endpoint.
    
    Args:
        graphql_endpoint: The WordPress GraphQL endpoint URL
        query: GraphQL query string
        variables: Optional variables for the GraphQL query
        headers: Optional HTTP headers for authentication or custom headers
        
    Returns:
        Dictionary containing GraphQL response data if successful, None otherwise
    """
    try:
        # Prepare request payload
        payload = {
            "query": query
        }
        
        if variables:
            payload["variables"] = variables
        
        # Prepare headers
        request_headers = {
            "Content-Type": "application/json"
        }
        
        if headers:
            request_headers.update(headers)
        
        # Make GraphQL request
        logger.info(f"Fetching data from WordPress GraphQL endpoint: {graphql_endpoint}")
        response = requests.post(
            graphql_endpoint,
            json=payload,
            headers=request_headers,
            timeout=30
        )
        
        # Check response status
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Check for GraphQL errors
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return None
        
        logger.info("Successfully fetched data from WordPress GraphQL endpoint")
        return data.get("data")
        
    except requests.exceptions.Timeout:
        logger.error("Request timeout while fetching WordPress data")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error while fetching WordPress data: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error fetching WordPress GraphQL data: {str(e)}", exc_info=True)
        return None


def fetch_wordpress_posts(
    graphql_endpoint: str,
    first: int = 10,
    after: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch WordPress posts using GraphQL.
    
    Args:
        graphql_endpoint: The WordPress GraphQL endpoint URL
        first: Number of posts to fetch (default: 10)
        after: Cursor for pagination
        headers: Optional HTTP headers for authentication
        
    Returns:
        Dictionary containing posts data if successful, None otherwise
    """
    query = """
    query GetPosts($first: Int!, $after: String) {
        posts(first: $first, after: $after) {
            pageInfo {
                hasNextPage
                endCursor
            }
            nodes {
                id
                title
                content
                excerpt
                date
                modified
                slug
                status
                author {
                    node {
                        name
                        email
                    }
                }
                categories {
                    nodes {
                        name
                        slug
                    }
                }
                tags {
                    nodes {
                        name
                        slug
                    }
                }
                featuredImage {
                    node {
                        sourceUrl
                        altText
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "first": first
    }
    
    if after:
        variables["after"] = after
    
    return fetch_wordpress_graphql(graphql_endpoint, query, variables, headers)


def fetch_wordpress_pages(
    graphql_endpoint: str,
    first: int = 10,
    after: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch WordPress pages using GraphQL.
    
    Args:
        graphql_endpoint: The WordPress GraphQL endpoint URL
        first: Number of pages to fetch (default: 10)
        after: Cursor for pagination
        headers: Optional HTTP headers for authentication
        
    Returns:
        Dictionary containing pages data if successful, None otherwise
    """
    query = """
    query GetPages($first: Int!, $after: String) {
        pages(first: $first, after: $after) {
            pageInfo {
                hasNextPage
                endCursor
            }
            nodes {
                id
                title
                content
                excerpt
                date
                modified
                slug
                status
                author {
                    node {
                        name
                        email
                    }
                }
                featuredImage {
                    node {
                        sourceUrl
                        altText
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "first": first
    }
    
    if after:
        variables["after"] = after
    
    return fetch_wordpress_graphql(graphql_endpoint, query, variables, headers)


def fetch_all_wordpress_posts(
    graphql_endpoint: str,
    headers: Optional[Dict[str, str]] = None,
    batch_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch all WordPress posts with pagination.
    
    Args:
        graphql_endpoint: The WordPress GraphQL endpoint URL
        headers: Optional HTTP headers for authentication
        batch_size: Number of posts to fetch per request
        
    Returns:
        List of all posts
    """
    all_posts = []
    has_next_page = True
    after_cursor = None
    
    try:
        while has_next_page:
            result = fetch_wordpress_posts(graphql_endpoint, batch_size, after_cursor, headers)
            
            if not result or "posts" not in result:
                logger.warning("No more posts to fetch or error occurred")
                break
            
            posts_data = result["posts"]
            all_posts.extend(posts_data.get("nodes", []))
            
            page_info = posts_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor")
            
            logger.info(f"Fetched {len(posts_data.get('nodes', []))} posts. Total: {len(all_posts)}")
        
        logger.info(f"Successfully fetched all {len(all_posts)} posts from WordPress")
        return all_posts
        
    except Exception as e:
        logger.error(f"Error fetching all WordPress posts: {str(e)}", exc_info=True)
        return all_posts
