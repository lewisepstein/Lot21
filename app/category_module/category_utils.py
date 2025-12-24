from typing import List, Dict, Any, Optional

import pandas as pd

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.helpers import (
    convert_datetime_to_formatted_string,
)
from models.categories import Category
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)


def get_last_updated(row):
    """Get the last updated datetime."""
    return (
        row['updated_on']
        if pd.notnull(row['updated_on']) and row['updated_on'] is not None
        else row['created_on']
    )


def get_categories_list() -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve list of active categories.
    
    Returns:
        List of category dictionaries if found, None otherwise
    """
    try:
        db = PostgresDB()
        categories = db.read(
            'categories',
            conditions={
                'is_active': True,
                'deleted_on': None,
                'is_root': False
            },
            columns=['id', 'category_name']
        )

        if not categories:
            logger.info("No active categories found")
            return None, "No active categories found"
        
        return categories, None
        
    except Exception as e:
        logger.error(f"Error retrieving categories: {e}")
        return None, "Unable to retrieve categories"


def get_parent_categories(is_parent = True, is_root=True, is_active=None) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve list of parent categories.
    
    Returns:
        List of parent category dictionaries if found, None otherwise
    """
    try:
        db = PostgresDB()
        
        # Print the query conditions for debugging
        conditions = {
            'is_parent': is_parent,
            'is_root': is_root,
            'deleted_on': None
        }

        if is_active is not None:
            conditions['is_active'] = is_active

        categories = db.read(
            'categories',
            conditions=conditions,
            columns=['id', 'category_name']
        )

        if not categories:
            logger.info("No parent categories found")
            return []
        
        logger.info(f"Retrieved {len(categories)} parent categories")
        return categories
        
    except Exception as e:
        logger.error(f"Error retrieving parent categories: {e}")
        return []


def check_root_exists() -> bool:
    """
    Check if a root category already exists in the database.
    
    Returns:
        True if root category exists, False otherwise
    """
    try:
        db = PostgresDB()
        root_categories = db.read(
            'categories',
            conditions={
                'is_root': True,
                'is_active': True,
                'deleted_on': None
            },
            limit=1
        )
        
        exists = root_categories is not None and len(root_categories) > 0
        logger.info(f"Root category exists: {exists}")
        return exists
        
    except Exception as e:
        logger.error(f"Error checking root category existence: {e}")
        return False


def create_category_record(
    category_name: str,
    is_parent: bool = False,
    parent_id: Optional[int] = None,
    is_root: bool = False,
    is_active: bool = True
) -> Optional[Category]:
    """
    Create a new category record in the database.
    
    Args:
        category_name: Name of the category
        is_parent: Flag indicating if this is a parent category
        parent_id: ID of the parent category (nullable)
        is_root: Flag indicating if this is a root category
        is_active: Flag indicating if the category is active
        
    Returns:
        Category object if successful, None otherwise
    """
    try:
        db = PostgresDB()
        
        # Prepare category data
        category_dict = {
            'category_name': category_name,
            'is_parent': is_parent,
            'parent_id': parent_id,
            'is_root': is_root,
            'is_active': is_active
        }
        
        # Create category in database
        result = db.create('categories', category_dict)
        
        if result:
            logger.info(f"Successfully created category: {category_name}")
            # Fetch the created category to return full object
            category = db.read(
                'categories',
                conditions={'id': result},
                limit=1
            )
            
            if category:
                # Convert to Category object
                category_data = category[0]
                return Category(**category_data)
        
        logger.error(f"Failed to create category: {category_name}")
        return None
        
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        return None
    
def category_exists(category_id: int) -> bool:
    """
    Check if a category with the given ID exists and is active.
    
    Args:
        category_id: ID of the category to check
        
    Returns:
        True if category exists and is active, False otherwise
    """
    try:
        db = PostgresDB()
        category = db.read(
            'categories',
            conditions={
                'id': category_id,
                'is_active': True,
                'deleted_on': None
            },
            limit=1
        )
        
        exists = category is not None and len(category) > 0
        logger.info(f"Category with ID {category_id} exists: {exists}")
        return exists
        
    except Exception as e:
        logger.error(f"Error checking category existence: {e}")
        return False
    
def deactivate_category(category_id: int) -> bool:
    """
    Deactivate a category by setting its is_active flag to False.
    
    Args:
        category_id: ID of the category to deactivate
        
    Returns:
        True if deactivation was successful, False otherwise
    """
    try:
        db = PostgresDB()
        update_result = db.update(
            'categories',
            conditions={'id': category_id},
            updates={'is_active': False}
        )
        
        if update_result:
            logger.info(f"Successfully deactivated category with ID {category_id}")
            return True
        
        logger.error(f"Failed to deactivate category with ID {category_id}")
        return False
        
    except Exception as e:
        logger.error(f"Error deactivating category: {e}")
        return False
    
def get_category_by_id(category_id: int) -> Optional[Category]:
    """
    Retrieve a category by its ID.
    
    Args:
        category_id: ID of the category to retrieve
        
    Returns:
        Category object if found, None otherwise
    """
    try:
        db = PostgresDB()
        category = db.read(
            'categories',
            conditions={
                'id': category_id,
                'deleted_on': None
            },
            limit=1
        )
        
        if category:
            logger.info(f"Retrieved category with ID {category_id}")
            category_data = category[0]
            return Category(**category_data)
        
        logger.info(f"No category found with ID {category_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving category by ID: {e}")
        return None