import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)


def parse_wordpress_xml(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse WordPress XML export file and extract post data.
    
    Args:
        file_path: Path to the WordPress XML export file
        
    Returns:
        List of dictionaries containing post data if successful, None otherwise
    """
    try:
        # Check if file exists
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        # Parse XML file
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Define namespaces
        namespaces = {
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'wp': 'http://wordpress.org/export/1.2/',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'excerpt': 'http://wordpress.org/export/1.2/excerpt/'
        }
        
        posts = []
        
        # Find all items (posts/pages)
        for item in root.findall('.//item'):
            try:
                # Get post type
                post_type = item.find('wp:post_type', namespaces)
                post_type_value = post_type.text if post_type is not None else None
                
                # Get post status
                post_status = item.find('wp:status', namespaces)
                post_status_value = post_status.text if post_status is not None else None
                
                # Process published posts (including custom post types like 'lot_projects')
                # Accept both 'post' and custom post types, but filter out 'page', 'attachment', 'nav_menu_item', etc.
                excluded_types = ['attachment', 'nav_menu_item', 'revision', 'wp_global_styles']
                
                if (post_status_value == 'publish' and 
                    post_type_value and 
                    post_type_value not in excluded_types):
                    # Extract basic fields
                    title = item.find('title')
                    title_text = title.text if title is not None else ""
                    
                    # Extract content
                    content = item.find('content:encoded', namespaces)
                    content_text = content.text if content is not None else ""
                    
                    # Extract excerpt
                    excerpt = item.find('excerpt:encoded', namespaces)
                    excerpt_text = excerpt.text if excerpt is not None else ""
                    
                    # Extract post metadata
                    post_id = item.find('wp:post_id', namespaces)
                    post_id_value = post_id.text if post_id is not None else None
                    
                    post_date = item.find('wp:post_date', namespaces)
                    post_date_value = post_date.text if post_date is not None else None
                    
                    post_name = item.find('wp:post_name', namespaces)
                    post_name_value = post_name.text if post_name is not None else ""
                    
                    # Extract author
                    creator = item.find('dc:creator', namespaces)
                    creator_value = creator.text if creator is not None else ""
                    
                    # Extract categories
                    categories = []
                    for category in item.findall('category[@domain="category"]'):
                        if category.text:
                            categories.append({
                                'name': category.text,
                                'nicename': category.get('nicename', '')
                            })
                    
                    # Extract tags
                    tags = []
                    for tag in item.findall('category[@domain="post_tag"]'):
                        if tag.text:
                            tags.append({
                                'name': tag.text,
                                'nicename': tag.get('nicename', '')
                            })
                    
                    # Extract postmeta (custom fields)
                    postmeta = []
                    for meta in item.findall('wp:postmeta', namespaces):
                        meta_key = meta.find('wp:meta_key', namespaces)
                        meta_value = meta.find('wp:meta_value', namespaces)
                        
                        if meta_key is not None and meta_value is not None:
                            postmeta.append({
                                'key': meta_key.text if meta_key.text else "",
                                'value': meta_value.text if meta_value.text else ""
                            })
                    
                    # Build post dictionary
                    post_data = {
                        'post_id': post_id_value,
                        'title': title_text,
                        'post_name': post_name_value,
                        'content': content_text,
                        'excerpt': excerpt_text,
                        'author': creator_value,
                        'post_date': post_date_value,
                        'post_type': post_type_value,
                        'post_status': post_status_value,
                        'categories': categories,
                        'tags': tags,
                        'postmeta': postmeta
                    }
                    
                    posts.append(post_data)
                    
            except Exception as e:
                logger.error(f"Error parsing individual post: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"Successfully parsed {len(posts)} posts from WordPress XML")
        return posts
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error parsing WordPress XML file: {str(e)}", exc_info=True)
        return None


def extract_post_blocks(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract WordPress block data from posts.
    
    Args:
        posts: List of post dictionaries from parse_wordpress_xml
        
    Returns:
        List of dictionaries containing post titles and their block content
    """
    try:
        posts_with_blocks = []
        
        for post in posts:
            # Get postmeta blocks
            blocks_content = []
            
            for meta in post.get('postmeta', []):
                meta_key = meta.get('key', '')
                meta_value = meta.get('value', '')
                
                # WordPress blocks are typically stored in postmeta
                # Look for block-related meta keys or content blocks
                if meta_value and len(meta_value.strip()) > 0:
                    blocks_content.append({
                        'meta_key': meta_key,
                        'content': meta_value
                    })
            
            post_blocks = {
                'post_id': post.get('post_id'),
                'title': post.get('title'),
                'post_name': post.get('post_name'),
                'main_content': post.get('content'),
                'excerpt': post.get('excerpt'),
                'author': post.get('author'),
                'post_date': post.get('post_date'),
                'categories': post.get('categories', []),
                'tags': post.get('tags', []),
                'blocks': blocks_content
            }
            
            posts_with_blocks.append(post_blocks)
        
        logger.info(f"Extracted blocks from {len(posts_with_blocks)} posts")
        return posts_with_blocks
        
    except Exception as e:
        logger.error(f"Error extracting post blocks: {str(e)}", exc_info=True)
        return []


def get_posts_by_category(posts: List[Dict[str, Any]], category_name: str) -> List[Dict[str, Any]]:
    """
    Filter posts by category name.
    
    Args:
        posts: List of post dictionaries
        category_name: Category name to filter by
        
    Returns:
        List of posts matching the category
    """
    try:
        filtered_posts = []
        
        for post in posts:
            categories = post.get('categories', [])
            for category in categories:
                if category.get('name', '').lower() == category_name.lower():
                    filtered_posts.append(post)
                    break
        
        logger.info(f"Found {len(filtered_posts)} posts in category '{category_name}'")
        return filtered_posts
        
    except Exception as e:
        logger.error(f"Error filtering posts by category: {str(e)}", exc_info=True)
        return []


def get_all_categories(posts: List[Dict[str, Any]]) -> List[str]:
    """
    Extract all unique categories from posts.
    
    Args:
        posts: List of post dictionaries
        
    Returns:
        List of unique category names
    """
    try:
        categories = set()
        
        for post in posts:
            for category in post.get('categories', []):
                cat_name = category.get('name')
                if cat_name:
                    categories.add(cat_name)
        
        category_list = sorted(list(categories))
        logger.info(f"Found {len(category_list)} unique categories")
        return category_list
        
    except Exception as e:
        logger.error(f"Error extracting categories: {str(e)}", exc_info=True)
        return []


def parse_and_extract_wordpress_data(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Complete workflow to parse WordPress XML and extract all data.
    
    Args:
        file_path: Path to the WordPress XML export file
        
    Returns:
        Dictionary containing posts, categories, and extracted blocks
    """
    try:
        # Parse XML file
        posts = parse_wordpress_xml(file_path)
        
        if not posts:
            logger.warning("No posts found in XML file")
            return None
        
        # Extract blocks from posts
        posts_with_blocks = extract_post_blocks(posts)
        
        # Get all categories
        categories = get_all_categories(posts)
        
        result = {
            'total_posts': len(posts),
            'posts': posts_with_blocks,
            'categories': categories,
            'posts_raw': posts
        }
        
        logger.info(f"Successfully extracted WordPress data: {len(posts)} posts, {len(categories)} categories")
        return result
        
    except Exception as e:
        logger.error(f"Error in complete WordPress data extraction: {str(e)}", exc_info=True)
        return None


def parse_policies_xml(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse WordPress policies XML export file and extract policy data.
    Uses the base parse_wordpress_xml function and adds policy-specific processing.
    
    Args:
        file_path: Path to the WordPress policies XML export file
        
    Returns:
        List of dictionaries containing policy data if successful, None otherwise
    """
    try:
        # Reuse the base parsing function
        posts = parse_wordpress_xml(file_path)
        
        if not posts:
            return None
        
        # Filter only lot_policies post type and add policy-specific processing
        policies = []
        
        for post in posts:
            if post.get('post_type') == 'lot_policies':
                # Extract and organize policy-specific data from postmeta
                # Exclude metadata tags that start with underscore or have blank values
                policy_list = []
                resources = []
                
                for meta in post.get('postmeta', []):
                    key = meta.get('key', '')
                    value = meta.get('value', '')
                    
                    # Skip if key starts with underscore or value is blank
                    if key.startswith('_') or not value or not value.strip():
                        continue
                    
                    # Extract policy list items
                    if key.startswith('policy_list_'):
                        parts = key.split('_')
                        if len(parts) >= 3 and parts[2].isdigit():
                            index = int(parts[2])
                            field_name = '_'.join(parts[3:]) if len(parts) > 3 else 'value'
                            
                            # Ensure the policy_list has enough entries
                            while len(policy_list) <= index:
                                policy_list.append({})
                            
                            policy_list[index][field_name] = value
                    
                    # Extract resources items
                    if key.startswith('resources_'):
                        parts = key.split('_')
                        if len(parts) >= 2 and parts[1].isdigit():
                            index = int(parts[1])
                            field_name = '_'.join(parts[2:]) if len(parts) > 2 else 'value'
                            
                            # Ensure resources has enough entries
                            while len(resources) <= index:
                                resources.append({})
                            
                            resources[index][field_name] = value
                
                # Add policy-specific fields to the post data
                post['policy_list'] = policy_list
                post['resources'] = resources
                policies.append(post)
        
        logger.info(f"Successfully extracted {len(policies)} policies from WordPress XML")
        return policies
        
    except Exception as e:
        logger.error(f"Error parsing WordPress policies XML file: {str(e)}", exc_info=True)
        return None


def extract_policy_blocks(policies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract and organize policy data with structured blocks.
    
    Args:
        policies: List of policy dictionaries from parse_policies_xml
        
    Returns:
        List of dictionaries containing organized policy data
    """
    try:
        policies_organized = []
        
        for policy in policies:
            # Filter postmeta to exclude underscore-prefixed keys and blank values
            filtered_metadata = [
                meta for meta in policy.get('postmeta', [])
                if not meta.get('key', '').startswith('_') 
                and meta.get('value', '') 
                and meta.get('value', '').strip()
            ]
            
            # Organize policy data
            organized_policy = {
                'post_id': policy.get('post_id'),
                'title': policy.get('title'),
                'post_name': policy.get('post_name'),
                'excerpt': policy.get('excerpt'),
                'content': policy.get('content'),
                'author': policy.get('author'),
                'post_date': policy.get('post_date'),
                'menu_order': policy.get('menu_order'),
                'policy_list': policy.get('policy_list', []),
                'resources': policy.get('resources', []),
                'all_metadata': filtered_metadata
            }
            
            policies_organized.append(organized_policy)
        
        logger.info(f"Organized {len(policies_organized)} policies")
        return policies_organized
        
    except Exception as e:
        logger.error(f"Error organizing policy blocks: {str(e)}", exc_info=True)
        return []


def parse_and_extract_policies_data(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Complete workflow to parse WordPress policies XML and extract all data.
    
    Args:
        file_path: Path to the WordPress policies XML export file
        
    Returns:
        Dictionary containing policies and extracted data
    """
    try:
        # Parse XML file
        policies = parse_policies_xml(file_path)
        
        if not policies:
            logger.warning("No policies found in XML file")
            return None
        
        # Extract and organize policy blocks
        policies_organized = extract_policy_blocks(policies)
        
        result = {
            'total_policies': len(policies),
            'policies': policies_organized,
            'policies_raw': policies
        }
        
        logger.info(f"Successfully extracted policies data: {len(policies)} policies")
        return result
        
    except Exception as e:
        logger.error(f"Error in complete policies data extraction: {str(e)}", exc_info=True)
        return None


if __name__ == "__main__":
    # Configure logging to see debug messages
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test policies parsing
    policies_file = "/home/lawrence/Desktop/py_projects/lot21_ai_project/external_sources/lot21_policies.xml"
    
    print(f"\n{'='*70}")
    print("PARSING POLICIES XML")
    print(f"{'='*70}")
    print(f"File: {policies_file}")
    print(f"File exists: {Path(policies_file).exists()}")
    
    policies_results = parse_and_extract_policies_data(policies_file)
    
    if policies_results:
        print(f"\n{'='*70}")
        print("POLICIES PARSING RESULTS")
        print(f"{'='*70}")
        print(f"Total Policies: {policies_results['total_policies']}")
        
        if policies_results['policies']:
            print(f"\n{'='*70}")
            print("FIRST POLICY - COMPLETE DETAILS")
            print(f"{'='*70}")
            
            # Get first policy
            policy = policies_results['policies'][0]
            
            print(f"\n{'#'*70}")
            print(f"BASIC INFORMATION")
            print(f"{'#'*70}")
            print(f"Title: {policy['title']}")
            print(f"Post ID: {policy['post_id']}")
            print(f"Post Name: {policy['post_name']}")
            print(f"Author: {policy['author']}")
            print(f"Post Date: {policy['post_date']}")
            print(f"Menu Order: {policy['menu_order']}")
            
            print(f"\n{'#'*70}")
            print(f"EXCERPT")
            print(f"{'#'*70}")
            print(policy['excerpt'])
            
            print(f"\n{'#'*70}")
            print(f"CONTENT")
            print(f"{'#'*70}")
            print(policy['content'])
            
            print(f"\n{'#'*70}")
            print(f"POLICY LIST ITEMS ({len(policy['policy_list'])} items)")
            print(f"{'#'*70}")
            for i, item in enumerate(policy['policy_list'], 1):
                print(f"\n{'-'*70}")
                print(f"POLICY ITEM {i}")
                print(f"{'-'*70}")
                for key, value in sorted(item.items()):
                    print(f"{key}: {value}")
            
            print(f"\n{'#'*70}")
            print(f"RESOURCES ({len(policy['resources'])} items)")
            print(f"{'#'*70}")
            for i, resource in enumerate(policy['resources'], 1):
                print(f"\n{'-'*70}")
                print(f"RESOURCE {i}")
                print(f"{'-'*70}")
                for key, value in sorted(resource.items()):
                    print(f"{key}: {value}")
            
            print(f"\n{'#'*70}")
            print(f"ALL METADATA ({len(policy['all_metadata'])} items)")
            print(f"{'#'*70}")
            for i, meta in enumerate(policy['all_metadata'], 1):
                print(f"\n{i}. {meta['key']}: {meta['value']}")
    else:
        print("\nNo policies results returned. Check the logs above for errors.")
    
    # Also test projects parsing for comparison
    print(f"\n\n{'='*70}")
    print("PARSING PROJECTS XML")
    print(f"{'='*70}")
    
    projects_file = "/home/lawrence/Desktop/py_projects/lot21_ai_project/external_sources/lot21_projects.xml"
    print(f"File: {projects_file}")
    print(f"File exists: {Path(projects_file).exists()}")
    
    projects_results = parse_and_extract_wordpress_data(projects_file)
    
    if projects_results:
        print(f"\nTotal Projects: {projects_results['total_posts']}")
        print(f"Total Categories: {len(projects_results['categories'])}")
    else:
        print("\nNo projects results returned.")