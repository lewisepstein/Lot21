from typing import List, Dict, Any, Optional
import pandas as pd
import uuid
import tiktoken

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

from weaviate_module.weaviate_utils import (
    load_data_with_tracking,
    delete_chunks_from_weaviate,
    chunk_text,
    load_chunks_to_weaviate,
    create_weaviate_version_snapshot
)
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
            columns=['id', 'page_name', 'category_id', 'created_on', 'updated_on', 'description']
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
        # if scrape_data and content and source_url:
        try:
            logger.info(f"Loading scraped content to Weaviate for page {page_id}")
            weaviate_result = load_data_with_tracking(
                scraped_content=content,
                collection_name="training_data",
                source_url=source_url,
                user_id=created_by,
                description=description,
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


def get_page_by_id(page_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single page by its ID.
    
    Args:
        page_id: The ID of the page to retrieve
        
    Returns:
        Dictionary containing page details if found, None otherwise
    """
    try:
        db = PostgresDB()
        
        pages = db.read(
            'pages',
            conditions={
                'id': page_id,
                'deleted_on': None
            },
            columns=['id', 'page_name', 'category_id', 'is_active', 
                    'source_url', 'description', 'created_on', 'updated_on']
        )
        
        if not pages or len(pages) == 0:
            logger.warning(f"Page with ID {page_id} not found")
            return None
        
        page = pages[0]

        print("Retrieved page:", page)
        
        # Get content from content table
        content_data = db.read(
            'content',
            conditions={
                'page_id': page_id,
                'deleted_on': None
            },
            columns=['generated_content']
        )
        
        content = content_data[0]['generated_content'] if content_data and len(content_data) > 0 else None
        
        # Convert to dictionary with proper formatting
        page_dict = {
            'id': page['id'],
            'page_name': page['page_name'],
            'category_id': page['category_id'] if page['category_id'] else None,
            'is_active': page['is_active'],
            'content': content,
            'source_url': page['source_url'],
            'description': page['description'],
            'created_on': convert_datetime_to_formatted_string(page['created_on']) if page.get('created_on') else None,
            'updated_on': convert_datetime_to_formatted_string(page['updated_on']) if page.get('updated_on') else None
        }
        
        logger.info(f"Retrieved page: {page['page_name']} (ID: {page_id})")
        return page_dict
        
    except Exception as e:
        logger.error(f"Error retrieving page {page_id}: {e}", exc_info=True)
        return None


def update_page(
    page_id: int,
    page_name: Optional[str] = None,
    category_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    content: Optional[str] = None,
    source_url: Optional[str] = None,
    description: Optional[str] = None,
    updated_by: Optional[int] = None
) -> Dict[str, Any]:
    """
    Update an existing page record, content, and weaviate data.
    Follows the same pattern as create_page but updates existing records.
    Note: Scraping is only available during page creation, not updates.
    
    Args:
        page_id: The ID of the page to update
        page_name: Optional new page name
        category_id: Optional new category ID
        is_active: Optional new active status
        content: Optional new content
        source_url: Optional new source URL (informational only, not used for scraping)
        description: Optional new description
        updated_by: User ID who is updating the page
        
    Returns:
        Dictionary containing updated page details
        
    Raises:
        ValueError: If page doesn't exist or validation fails
    """
    ENCODING = "cl100k_base"
    
    try:
        db = PostgresDB()
        
        # Check if page exists
        existing_page = db.read(
            'pages',
            conditions={'id': page_id, 'deleted_on': None}
        )
        
        if not existing_page or len(existing_page) == 0:
            raise ValueError(f"Page with ID {page_id} not found")
        
        old_page = existing_page[0]
        
        # Get existing content record
        existing_content = db.read(
            'content',
            conditions={'page_id': page_id, 'deleted_on': None}
        )
        old_content_record = existing_content[0] if existing_content and len(existing_content) > 0 else None
        old_content = old_content_record['generated_content'] if old_content_record else None
        
        # Get existing weaviate_data record
        existing_weaviate = db.read(
            'weaviate_data',
            conditions={'page_id': page_id, 'deleted_at': None}
        )
        old_weaviate_record = existing_weaviate[0] if existing_weaviate and len(existing_weaviate) > 0 else None
        
        # Use provided content directly (no scraping in updates)
        final_content = content
        
        # Build page update data
        page_update_data = {}
        
        if page_name is not None:
            if not page_name.strip():
                raise ValueError("Page name cannot be empty")
            page_update_data['page_name'] = page_name.strip()
        
        if category_id is not None:
            page_update_data['category_id'] = category_id if category_id > 0 else None
        
        if is_active is not None:
            page_update_data['is_active'] = is_active
        
        if source_url is not None:
            if source_url.strip():
                if not validate_url(source_url):
                    raise ValueError("Invalid source URL format")
                page_update_data['source_url'] = source_url.strip()
            else:
                page_update_data['source_url'] = None
        
        if description is not None:
            page_update_data['description'] = description.strip() if description.strip() else None
        
        # Update page record
        if page_update_data:
            db.update(
                table_name='pages',
                data=page_update_data,
                conditions={'id': page_id}
            )
            logger.info(f"Updated page record {page_id}")
        
        # Handle content and weaviate updates if content changed
        if final_content is not None and final_content != old_content:
            logger.info(f"Content changed for page {page_id}, updating content and Weaviate")
            
            # Update or create content record
            if old_content_record:
                # Update existing content
                db.update(
                    table_name='content',
                    data={
                        'generated_content': final_content,
                        'prompt_data': None,
                        'action': ContentActionEnum.DRAFT.value
                    },
                    conditions={'id': old_content_record['id']}
                )
                logger.info(f"Updated content record {old_content_record['id']}")
            elif category_id or old_page.get('category_id'):
                # Create new content record
                actual_category_id = category_id if category_id is not None else old_page.get('category_id')
                if actual_category_id:
                    content_record = create_content_record(
                        category_id=actual_category_id,
                        prompt_data=None,
                        action=ContentActionEnum.DRAFT,
                        generated_content=final_content,
                        page_id=page_id,
                        created_by=updated_by
                    )
                    logger.info(f"Created content record {content_record.get('id')} for page {page_id}")
            
            # Handle Weaviate updates if content exists
            if old_weaviate_record:
                # Delete old chunks and create new ones (similar to agent update pattern)
                old_data_details = old_weaviate_record.get('data_details') or {}
                old_doc_id = old_data_details.get('doc_id')
                collection_name = old_weaviate_record.get('collection_name', 'training_data')
                
                # Store old values for versioning
                old_weaviate_data = {
                    "content": old_weaviate_record.get('content'),
                    "description": old_weaviate_record.get('description'),
                    "no_of_lines": old_weaviate_record.get('no_of_lines'),
                    "no_of_tokens": old_weaviate_record.get('no_of_tokens'),
                    "no_of_characters": old_weaviate_record.get('no_of_characters'),
                    "data_details": old_weaviate_record.get('data_details')
                }
                
                # Delete old chunks
                if old_doc_id:
                    try:
                        logger.info(f"Deleting old chunks from Weaviate: doc_id='{old_doc_id}'")
                        delete_result = delete_chunks_from_weaviate(
                            collection_name=collection_name,
                            doc_id=old_doc_id
                        )
                        logger.info(f"Deleted {delete_result.get('chunks_deleted', 0)} old chunks")
                    except Exception as weaviate_error:
                        logger.error(f"Error deleting old chunks: {str(weaviate_error)}")
                
                # Generate new doc_id and chunk the content
                new_doc_id = str(uuid.uuid4())
                logger.info("Chunking updated content...")
                chunks = chunk_text(final_content, max_tokens=400, overlap=50)
                chunks_count = len(chunks)
                logger.info(f"Created {chunks_count} new chunks")
                
                # Calculate statistics
                no_of_characters = len(final_content)
                no_of_lines = len(final_content.split('\n'))
                try:
                    enc = tiktoken.get_encoding(ENCODING)
                    no_of_tokens = len(enc.encode(final_content))
                except Exception as e:
                    logger.warning(f"Failed to calculate tokens: {e}")
                    no_of_tokens = None
                
                # Load new chunks to Weaviate
                from datetime import datetime
                start_time = datetime.now(datetime.now().astimezone().tzinfo)
                
                load_chunks_to_weaviate(
                    chunks=chunks,
                    collection_name=collection_name,
                    doc_id=new_doc_id,
                    description=description or old_weaviate_record.get('description', '')
                )
                
                end_time = datetime.now(datetime.now().astimezone().tzinfo)
                processing_duration = int((end_time - start_time).total_seconds())
                
                # Update weaviate_data record
                data_details_json = {
                    "doc_id": new_doc_id,
                    "chunks_created": chunks_count,
                    "collection_description": description or old_weaviate_record.get('description', '')
                }
                
                db.update(
                    table_name='weaviate_data',
                    data={
                        'content': final_content,
                        'description': description or old_weaviate_record.get('description'),
                        'no_of_lines': no_of_lines,
                        'no_of_tokens': no_of_tokens,
                        'no_of_characters': no_of_characters,
                        'data_details': data_details_json,
                        'processing_duration': processing_duration,
                        'error_msg': None
                    },
                    conditions={'id': old_weaviate_record['id']}
                )
                
                logger.info(f"Updated weaviate_data record {old_weaviate_record['id']}")
                
                # Create version snapshot
                new_weaviate_data = {
                    "content": final_content,
                    "description": description or old_weaviate_record.get('description'),
                    "no_of_lines": no_of_lines,
                    "no_of_tokens": no_of_tokens,
                    "no_of_characters": no_of_characters,
                    "data_details": data_details_json
                }
                
                try:
                    version_result = create_weaviate_version_snapshot(
                        weaviate_data_id=old_weaviate_record['id'],
                        user_id=old_weaviate_record.get('created_by'),
                        old_data=old_weaviate_data,
                        new_data=new_weaviate_data,
                        operation="UPDATE",
                        change_description=f"Page {page_id} content updated"
                    )
                    logger.info(f"Version snapshot created: {version_result}")
                except Exception as version_error:
                    logger.error(f"Failed to create version snapshot: {str(version_error)}")
        
        # Retrieve updated record
        updated_page = db.read(
            'pages',
            conditions={'id': page_id},
            columns=['id', 'page_name', 'category_id', 'is_active',
                    'source_url', 'description', 'created_on', 'updated_on']
        )[0]
        
        # Get updated content
        updated_content_data = db.read(
            'content',
            conditions={'page_id': page_id, 'deleted_on': None},
            columns=['generated_content']
        )
        updated_content = updated_content_data[0]['generated_content'] if updated_content_data and len(updated_content_data) > 0 else None
        
        logger.info(f"Successfully updated page: {updated_page['page_name']} (ID: {page_id})")
        
        return {
            'id': updated_page['id'],
            'page_name': updated_page['page_name'],
            'category_id': updated_page['category_id'],
            'is_active': updated_page['is_active'],
            'content': updated_content,
            'source_url': updated_page['source_url'],
            'description': updated_page['description'],
            'created_on': convert_datetime_to_formatted_string(updated_page['created_on']) if updated_page.get('created_on') else None,
            'updated_on': convert_datetime_to_formatted_string(updated_page['updated_on']) if updated_page.get('updated_on') else None
        }
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error updating page {page_id}: {e}", exc_info=True)
        raise ValueError(f"Failed to update page: {str(e)}")


def delete_page(page_id: int) -> None:
    """
    Hard delete a single page and all related records in a transaction.

    Steps:
    1. Check if page exists
    2. Delete from weaviate_data_versions
    3. Delete from weaviate_data
    4. Delete from content
    5. Delete from pages

    Args:
        page_id: Page ID to delete

    Raises:
        ValueError: If page does not exist
        Exception: If deletion fails
    """
    db = PostgresDB()

    try:
        
        # 1. Check if page exists
        page = db.read('pages', conditions={'id': page_id})
        if not page:
            raise ValueError(f"Page with ID {page_id} not found")
        
        weaviate = db.read(
            'weaviate_data',
            conditions={'page_id': page_id, 'deleted_at': None}
        )

        if weaviate:
            # Delete chunks from Weaviate
            data_details = weaviate[0].get('data_details') or {}
            doc_id = data_details.get('doc_id')
            collection_name = weaviate[0].get('collection_name', 'training_data')
            if doc_id:
                try:
                    logger.info(f"Deleting chunks from Weaviate for page {page_id}, doc_id='{doc_id}'")
                    delete_result = delete_chunks_from_weaviate(
                        collection_name=collection_name,
                        doc_id=doc_id
                    )
                    logger.info(f"Deleted {delete_result.get('chunks_deleted', 0)} chunks from Weaviate")
                except Exception as weaviate_error:
                    logger.error(f"Error deleting chunks from Weaviate: {str(weaviate_error)}")

            # 2. Delete related records
            db.delete('weaviate_data_versions', conditions={'weaviate_data_id': weaviate[0]['id']})

        db.delete('weaviate_data', conditions={'page_id': page_id})
        db.delete('content', conditions={'page_id': page_id})

        # 3. Delete page
        db.delete('pages', conditions={'id': page_id})

        logger.info(
            "Hard deleted page and related records for page_id=%s",
            page_id
        )

    except Exception as e:
        logger.exception("Failed to hard delete page_id=%s", page_id)
        logger.error(f"Error details: {str(e)}")
        raise


# def validate_page_name(page_name: str) -> bool:
#     """
#     Validate if the page name is unique (not already used).
    
#     Args:
#         page_name: The page name to validate
#     """
#     if not page_name or not page_name.strip():
#         return False

# def __create_page(    
#     page_name: str,
#     category_id: Optional[int] = None,
#     created_by: Optional[int] = None,
#     is_active: bool = True,
#     content: Optional[str] = None,
#     source_url: Optional[str] = None,
#     scrape_data: bool = False,
#     description: Optional[str] = None
# ) -> Dict[str, Any]:
#     pass


# def validate_category_id(category_id: Optional[int]) -> bool:
#     """
#     Validate if the category ID exists in the database.
    
#     Args:
#         category_id: The category ID to validate
#     """
#     if category_id is None:
#         return True  # No category specified is valid

#     try:
#         db = PostgresDB()
#         categories = db.read(
#             'categories',
#             conditions={
#                 'id': category_id,
#                 'deleted_on': None
#             }
#         )
        
#         exists = categories is not None and len(categories) > 0
#         logger.info(f"Category ID {category_id} exists: {exists}")
#         return exists
        
#     except Exception as e:
#         logger.error(f"Error validating category ID {category_id}: {e}")
#         return False


# def validate_source_url(source_url: str) -> Optional[bool]:
#     if source_url:
#         source_url = source_url.strip()
#         valid_source_url = validate_url(source_url)
#         if not valid_source_url:
#             return ValueError("Invalid URL format. Please provide a valid HTTP or HTTPS URL")
#         return True
#     return False

# def page_exists(page_name: str)-> Optional[bool]:
#     try:
#         db = PostgresDB()
#         existing_pages = db.read(
#             'pages',
#             conditions={
#                 'page_name': page_name.strip().lower,
#                 'deleted_on': None
#             }
#         )
        
#         if existing_pages and len(existing_pages) > 0:
#             raise ValueError("Page name already exists. Please choose a different name")

#         return True
#     except Exception as e:
#         logger.error(f"Error validating page name: {e}")
#         return False
        