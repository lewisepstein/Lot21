from typing import List, Dict, Any, Optional
import pandas as pd

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.helpers import (
    convert_datetime_to_formatted_string,
    validate_url,
)
from service_utils.log_management import get_logger
from data_ingestion_module.scrapper import (
    scrape_page,
    convert_to_wysiwyg_html,
)
from weaviate_module.weaviate_utils import load_scraped_data_with_tracking
from content_module.content_utils import create_content_record
from models.content import ContentActionEnum

# Set up logging
logger = get_logger(__name__)


def get_last_updated(row):
    """Get the last updated datetime."""
    return (
        row['updated_on']
        if pd.notnull(row['updated_on']) and row['updated_on'] is not None
        else row['created_on']
    )

def get_pages_list(category_id: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve list of active pages.
    
    Args:
        category_id: Optional category ID to filter pages by category
    
    Returns:
        List of page dictionaries if found, None otherwise
    """
    try:
        db = PostgresDB()
        
        # Build conditions
        conditions = {
            'is_active': True,
            'deleted_on': None
        }
        
        # Add category_id filter if provided
        if category_id is not None:
            conditions['category_id'] = category_id
        
        pages = db.read(
            'pages',
            conditions=conditions,
            columns=['id', 'page_name', 'category_id', 'created_on', 'updated_on']
        )

        if not pages:
            logger.info("No active pages found")
            return None, "No active pages found"
        
        df = pd.DataFrame(pages)
        
        df['last_updated_dt'] = df.apply(get_last_updated, axis=1)
        
        # Convert last_updated to display format
        df['last_updated_on'] = df['last_updated_dt'].apply(
            convert_datetime_to_formatted_string
        )
        
        # Drop columns
        df.drop('last_updated_dt', axis=1, inplace=True)
        df.drop('updated_on', axis=1, inplace=True)
        df.drop('created_on', axis=1, inplace=True)
        
        logger.info(f"Retrieved {len(pages)} pages")
        return df.to_dict('records'), f"Retrieved {len(pages)} pages"
        
    except Exception as e:
        logger.error(f"Error retrieving pages: {e}")
        return None, "Unable to retrieve pages"


def get_parent_pages() -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve list of parent pages.
    
    Returns:
        List of parent page dictionaries if found, None otherwise
    """
    try:
        db = PostgresDB()
        pages = db.read(
            'pages',
            conditions={
                'is_parent': True,
                'is_active': True,
                'deleted_on': None
            },
            columns=['id', 'page_name']
        )

        if not pages:
            logger.info("No parent pages found")
            return []
        
        logger.info(f"Retrieved {len(pages)} parent pages")
        return pages
        
    except Exception as e:
        logger.error(f"Error retrieving parent pages: {e}")
        return []


def check_root_exists() -> bool:
    """
    Check if a root page already exists in the database.
    
    Returns:
        True if root page exists, False otherwise
    """
    try:
        db = PostgresDB()
        root_pages = db.read(
            'pages',
            conditions={
                'is_root': True,
                'is_active': True,
                'deleted_on': None
            },
            limit=1
        )
        
        exists = root_pages is not None and len(root_pages) > 0
        logger.info(f"Root page exists: {exists}")
        return exists
        
    except Exception as e:
        logger.error(f"Error checking root page existence: {e}")
        return False


def create_page_record(
    page_name: str,
    category_id: Optional[int] = None,
    created_by: Optional[int] = None,
    is_active: bool = True,
    content: Optional[str] = None,
    source_url: Optional[str] = None,
    scrape_data: bool = False,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new page record in the database and a corresponding content entry.
    
    Args:
        page_name: Name of the page
        category_id: ID of the category (nullable)
        created_by: ID of the user who created the page (nullable)
        is_active: Flag indicating if the page is active
        content: Optional content text for the page
        source_url: Optional source URL for the page
        scrape_data: Flag indicating if data should be scraped from URL
        description: Optional description for the page
        
    Returns:
        Dictionary containing the created page record
        
    Raises:
        ValueError: If scrape_data is True but source_url is invalid or missing
        Exception: If database insert fails
    """
    try:
        # Validate URL if scrape_data is True
        if scrape_data:
            if not source_url:
                raise ValueError("Source URL is required when scrape data is enabled")
            
            # Validate URL format
            if not validate_url(source_url):
                raise ValueError("Invalid URL format. Please provide a valid HTTP or HTTPS URL")
            
            # Scrape content from URL
            try:
                logger.info(f"Scraping content from URL: {source_url}")
                scraped_data = scrape_page(source_url)
                scraped_html = convert_to_wysiwyg_html(scraped_data)

                logger.info(f"Scraped HTML Content length: {len(scraped_html)} characters")
                
                # Override content with scraped content
                content = scraped_html
                logger.info(f"Successfully scraped content from {source_url}")
            except Exception as scrape_error:
                logger.error(f"Failed to scrape content from {source_url}: {scrape_error}")
                raise ValueError(f"Failed to scrape content from URL: {str(scrape_error)}")
        
        db = PostgresDB()

        # Prepare page data
        page_dict = {
            'page_name': page_name,
            'created_by': created_by,
            'is_active': is_active,
            'source_url': source_url,
            'scrape_data': scrape_data,
            'description': description
        }

        if category_id is not None:
            page_dict['category_id'] = category_id

        # Log the data being inserted
        logger.info(f"Inserting page data: {page_dict}")

        
        # Create page in database
        page_record = db.create('pages', page_dict)
        
        if not page_record:
            raise Exception("Failed to create page")
        
        page_id = page_record['id']
        
        # Load scraped content to Weaviate if scraping was performed
        if scrape_data and content and source_url:
            try:
                logger.info(f"Loading scraped content to Weaviate for page {page_id}")
                weaviate_result = load_scraped_data_with_tracking(
                    scraped_content=content,
                    collection_name="training_data",
                    source_url=source_url,
                    user_id=created_by,
                    description=description or f"Scraped content for page: {page_name}",
                    page_id=page_id
                )
                logger.info(f"Loaded {weaviate_result['chunks_created']} chunks to Weaviate (record ID: {weaviate_result['record_id']})")
            except Exception as weaviate_error:
                logger.warning(f"Failed to load scraped content to Weaviate: {weaviate_error}")
                # Don't fail page creation if Weaviate loading fails
        
        # Create corresponding content entry (only if content is provided and category exists)
        if content and category_id is not None:
            try:
                # Create content record using content_utils function
                content_record = create_content_record(
                    category_id=category_id,
                    prompt_data=None,  # No prompt for scraped/manual content
                    action=ContentActionEnum.DRAFT,
                    user_id=created_by,
                    content_type=None
                )
                
                # Update the content record with page_id and generated_content
                db.update(
                    'content',
                    conditions={'id': content_record['id']},
                    data={
                        'page_id': page_id,
                        'generated_content': content
                    }
                )
                
                logger.info(f"Successfully created content entry (ID: {content_record['id']}) for page {page_id}")
            except Exception as e:
                logger.warning(f"Failed to create content entry for page {page_id}: {e}")
        elif category_id is None:
            logger.info(f"Page {page_id} created without category, skipping content entry creation")
        
        # Fetch the created page to return full object
        page = db.read(
            'pages',
            conditions={'id': page_id},
            limit=1
        )
        
        if not page:
            raise Exception("Failed to retrieve created page")
        
        logger.info(f"Successfully created page: {page_name} (ID: {page_id})")
        return page[0]
        
    except Exception as e:
        logger.error(f"Error creating page: {e}")
        raise


def get_page_statistics() -> Dict[str, Any]:
    """
    Get statistics about pages including counts for various categories.
    
    Returns:
        Dictionary containing page statistics
    """
    try:
        db = PostgresDB()
        
        # Get all pages (including inactive)
        all_pages = db.read(
            'pages',
            conditions={'deleted_on': None},
            columns=['id', 'page_name', 'category_id', 'is_active', 'created_on', 'updated_on']
        )
        
        if not all_pages:
            return {
                'assigned_pages': 0,
                'unassigned_pages': 0,
                'active_pages': 0,
                'inactive_pages': 0,
                'pages_with_content': 0,
                'pages_without_content': 0,
                'pages': []
            }
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(all_pages)
        
        # Get content counts per page
        content_counts = db.read(
            'content',
            conditions={'deleted_on': None},
            columns=['page_id']
        )
        
        # Create a set of page IDs that have content
        pages_with_content_ids = set()
        if content_counts:
            content_df = pd.DataFrame(content_counts)
            pages_with_content_ids = set(content_df[content_df['page_id'].notna()]['page_id'].unique())
        
        # Get category names
        categories = db.read(
            'categories',
            conditions={'deleted_on': None},
            columns=['id', 'category_name']
        )
        
        category_map = {}
        if categories:
            category_map = {cat['id']: cat['category_name'] for cat in categories}
        
        # Get Weaviate status for pages (latest status per page)
        weaviate_status_map = {}
        for page_id in df['id']:
            latest_weaviate = db.read(
                'weaviate_data',
                conditions={'deleted_at': None, 'page_id': int(page_id)},
                columns=['status'],
                order_by=[('created_at', False)],  # False = descending order
                limit=1
            )
            
            if latest_weaviate and len(latest_weaviate) > 0:
                status = latest_weaviate[0].get('status')
                logger.info(f"Page {page_id}: Raw status = {status}, Type = {type(status)}")
                
                # Extract status value from enum (always get the string value)
                if hasattr(status, 'value'):
                    status_value = status.value
                    logger.info(f"Page {page_id}: Extracted enum value = {status_value}")
                    weaviate_status_map[int(page_id)] = status_value
                elif isinstance(status, str):
                    logger.info(f"Page {page_id}: Using string status = {status}")
                    weaviate_status_map[int(page_id)] = status
                else:
                    status_str = str(status)
                    logger.info(f"Page {page_id}: Converting to string = {status_str}")
                    weaviate_status_map[int(page_id)] = status_str
        
        logger.info(f"Weaviate status map: {weaviate_status_map}")
        
        # Calculate statistics
        assigned_pages = len(df[df['category_id'].notna()])
        unassigned_pages = len(df[df['category_id'].isna()])
        active_pages = len(df[df['is_active']])
        inactive_pages = len(df[~df['is_active']])
        pages_with_content = len([pid for pid in df['id'] if pid in pages_with_content_ids])
        
        # Prepare detailed page list
        pages_list = []
        for _, row in df.iterrows():
            page_dict = {
                'id': row['id'],
                'page_name': row['page_name'],
                'category_id': row['category_id'] if pd.notna(row['category_id']) else None,
                'category_name': category_map.get(int(row['category_id'])) if pd.notna(row['category_id']) else None,
                'is_active': row['is_active'],
                'has_content': row['id'] in pages_with_content_ids,
                'weaviate_status': weaviate_status_map.get(row['id']),
                'created_on': convert_datetime_to_formatted_string(row['created_on']) if pd.notna(row['created_on']) else None,
                'updated_on': convert_datetime_to_formatted_string(row['updated_on']) if pd.notna(row['updated_on']) else None
            }
            pages_list.append(page_dict)
        
        return {
            'assigned_pages': assigned_pages,
            'unassigned_pages': unassigned_pages,
            'active_pages': active_pages,
            'inactive_pages': inactive_pages,
            'pages_with_content': pages_with_content,
            'pages_without_content': len(df) - pages_with_content,
            'pages': pages_list
        }
        
    except Exception as e:
        logger.error(f"Error getting page statistics: {e}")
        return {
            'assigned_pages': 0,
            'unassigned_pages': 0,
            'active_pages': 0,
            'inactive_pages': 0,
            'pages_with_content': 0,
            'pages_without_content': 0,
            'pages': []
        }
