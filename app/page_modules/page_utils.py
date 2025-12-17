from typing import List, Dict, Any, Optional
import logging

import pandas as pd

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.helpers import (
    convert_datetime_to_formatted_string,
)
from models.pages import Page

# Set up logging
logger = logging.getLogger(__name__)


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
    is_active: bool = True
) -> Dict[str, Any]:
    """
    Create a new page record in the database.
    
    Args:
        page_name: Name of the page
        category_id: ID of the category (nullable)
        created_by: ID of the user who created the page (nullable)
        is_active: Flag indicating if the page is active
        
    Returns:
        Dictionary containing the created page record
        
    Raises:
        Exception: If database insert fails
    """
    try:
        db = PostgresDB()
        
        # Prepare page data
        page_dict = {
            'page_name': page_name,
            'category_id': category_id,
            'created_by': created_by,
            'is_active': is_active
        }
        
        # Create page in database
        result = db.create('pages', page_dict)
        
        if not result:
            raise Exception("Failed to create page")
        
        # Fetch the created page to return full object
        page = db.read(
            'pages',
            conditions={'id': result},
            limit=1
        )
        
        if not page:
            raise Exception("Failed to retrieve created page")
        
        logger.info(f"Successfully created page: {page_name} (ID: {result})")
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
        
        # Calculate statistics
        assigned_pages = len(df[df['category_id'].notna()])
        unassigned_pages = len(df[df['category_id'].isna()])
        active_pages = len(df[df['is_active']])
        inactive_pages = len(df[not df['is_active']])
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
