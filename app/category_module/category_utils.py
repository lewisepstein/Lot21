from typing import List, Dict, Any, Optional
import logging

import pandas as pd

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.helpers import (
    convert_datetime_to_formatted_string,
)

# Set up logging
logger = logging.getLogger(__name__)


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
            columns=['id', 'category_name', 'created_on', 'updated_on']
        )

        if not categories:
            logger.info("No active categories found")
            return None, "No active categories found"
        
        df = pd.DataFrame(categories)
        
        df['last_updated_dt'] = df.apply(get_last_updated, axis=1)
        
        # Convert last_updated to display format
        df['last_updated_on'] = df['last_updated_dt'].apply(
            convert_datetime_to_formatted_string
        )
        
        # Drop columns
        df.drop('last_updated_dt', axis=1, inplace=True)
        df.drop('updated_on', axis=1, inplace=True)
        df.drop('created_on', axis=1, inplace=True)
        
        logger.info(f"Retrieved {len(categories)} categories")
        return df.to_dict('records'), f"Retrieved {len(categories)} categories"
        
    except Exception as e:
        logger.error(f"Error retrieving categories: {e}")
        return None, "Unable to retrieve categories"