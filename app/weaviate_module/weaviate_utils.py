"""
Weaviate utility functions.
Provides text chunking, embedding, and RAG prompt generation utilities.
"""
import os
import json
import tiktoken
from typing import List, Dict, Any, Tuple
from datetime import datetime
import uuid

from sqlalchemy import text

from service_utils.db_utils.weaviate_db import WeaviateDB
from service_utils.db_utils.pg_db import PostgresDB
from models.weaviate_data import WeaviateDataStatusEnum
from models.weaviate_data_versions import WeaviateDataVersion
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Token encoding for chunking
ENCODING = "cl100k_base"

# Initialize OpenAI if available
if OPENAI_API_KEY:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
    except ImportError:
        logger.warning("openai package not installed")
        openai = None
else:
    openai = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_text_statistics(text: str) -> Tuple[int, int, int]:
    """
    Calculate statistics for text content.
    
    Args:
        text: Text content to analyze
        
    Returns:
        Tuple of (no_of_characters, no_of_lines, no_of_tokens)
        
    Examples:
        >>> chars, lines, tokens = calculate_text_statistics("Sample text\\nLine 2")
        >>> print(f"Chars: {chars}, Lines: {lines}, Tokens: {tokens}")
    """
    no_of_characters = len(text)
    no_of_lines = len(text.split('\n'))
    
    # Calculate tokens
    try:
        enc = tiktoken.get_encoding(ENCODING)
        no_of_tokens = len(enc.encode(text))
    except Exception as e:
        logger.warning(f"Failed to calculate tokens: {e}")
        no_of_tokens = None
    
    return no_of_characters, no_of_lines, no_of_tokens


def create_weaviate_data_record(
    db: PostgresDB,
    collection_name: str,
    content: str,
    user_id: int,
    description: str = "",
    no_of_characters: int = 0,
    no_of_lines: int = 0,
    no_of_tokens: int = None,
    page_id: int = None,
    content_id: int = None
) -> Dict[str, Any]:
    """
    Create a weaviate_data database record with IN_PROGRESS status.
    
    Args:
        db: PostgresDB instance
        collection_name: Name of the Weaviate collection
        content: Text content being stored
        user_id: ID of the user creating the record
        description: Optional description
        no_of_characters: Number of characters in content
        no_of_lines: Number of lines in content
        no_of_tokens: Number of tokens in content (optional)
        page_id: Optional page ID reference
        content_id: Optional content ID reference
        
    Returns:
        Dictionary containing the created database record with start_time set
        
    Raises:
        Exception: If database insert fails
    """
    start_time = datetime.now(datetime.now().astimezone().tzinfo)
    
    weaviate_data_dict = {
        "collection_name": collection_name,
        "description": description,
        "content": content,
        "status": WeaviateDataStatusEnum.IN_PROGRESS.value,
        "no_of_lines": no_of_lines,
        "no_of_tokens": no_of_tokens,
        "no_of_characters": no_of_characters,
        "created_by": user_id
    }
    
    # Add optional foreign key references
    if page_id is not None:
        weaviate_data_dict["page_id"] = page_id
    if content_id is not None:
        weaviate_data_dict["content_id"] = content_id
    
    # Create new weaviate_data entry
    db_record = db.create("weaviate_data", weaviate_data_dict)
    
    if not db_record:
        raise Exception("Failed to create weaviate_data record")
    
    record_id = db_record["id"]
    
    # Update with start_time using raw SQL
    with db.engine.begin() as conn:
        conn.execute(
            text("UPDATE weaviate_data SET start_time = :start_time WHERE id = :id"),
            {"start_time": start_time, "id": record_id}
        )
    db_record["start_time"] = start_time
    
    logger.info(f"Created weaviate_data record with ID: {record_id}")
    return db_record


def update_weaviate_data_success(
    db: PostgresDB,
    record_id: int,
    start_time: datetime,
    doc_id: str,
    chunks_created: int,
    description: str = "",
    extra_details: Dict[str, Any] = None
) -> None:
    """
    Update weaviate_data record with COMPLETED status.
    
    Args:
        db: PostgresDB instance
        record_id: ID of the weaviate_data record
        start_time: Time when processing started
        doc_id: Document ID used in Weaviate
        chunks_created: Number of chunks created
        description: Description of the collection
        extra_details: Optional additional details to store in data_details JSON
    """
    end_time = datetime.now(datetime.now().astimezone().tzinfo)
    processing_duration = int((end_time - start_time).total_seconds())
    
    data_details = {
        "doc_id": doc_id,
        "chunks_created": chunks_created,
        "collection_description": description
    }
    
    if extra_details:
        data_details.update(extra_details)
    
    data_details_json = json.dumps(data_details)
    
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE weaviate_data 
                SET status = :status, 
                    end_time = :end_time, 
                    processing_duration = :processing_duration,
                    data_details = CAST(:data_details AS jsonb)
                WHERE id = :id
            """),
            {
                "status": WeaviateDataStatusEnum.COMPLETED.value,
                "end_time": end_time,
                "processing_duration": processing_duration,
                "data_details": data_details_json,
                "id": record_id
            }
        )
    logger.info(f"Updated weaviate_data record {record_id} with COMPLETED status")


def update_weaviate_data_error(
    db: PostgresDB,
    record_id: int,
    start_time: datetime,
    error_msg: str
) -> None:
    """
    Update weaviate_data record with ERROR status.
    
    Args:
        db: PostgresDB instance
        record_id: ID of the weaviate_data record
        start_time: Time when processing started
        error_msg: Error message to store
    """
    end_time = datetime.now(datetime.now().astimezone().tzinfo)
    processing_duration = int((end_time - start_time).total_seconds())
    
    with db.engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE weaviate_data 
                SET status = :status,
                    end_time = :end_time,
                    processing_duration = :processing_duration,
                    error_msg = :error_msg
                WHERE id = :id
            """),
            {
                "status": WeaviateDataStatusEnum.EXIT_WITH_ERROR.value,
                "end_time": end_time,
                "processing_duration": processing_duration,
                "error_msg": error_msg,
                "id": record_id
            }
        )
    logger.info(f"Updated weaviate_data record {record_id} with ERROR status")


# ============================================================================
# CHUNKING AND WEAVIATE OPERATIONS
# ============================================================================

def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> List[str]:
    """
    Chunk text into smaller pieces based on token count.
    
    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk (default: 400)
        overlap: Number of overlapping tokens between chunks (default: 50)
        
    Returns:
        List of text chunks
    """
    try:
        enc = tiktoken.get_encoding(ENCODING)
        toks = enc.encode(text)
        chunks = []
        i = 0
        while i < len(toks):
            chunk_toks = toks[i : i + max_tokens]
            chunk_text = enc.decode(chunk_toks)
            chunks.append(chunk_text)
            i += max_tokens - overlap
        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        # Fallback: simple character-based chunking
        chunk_size = max_tokens * 4  # Rough approximation
        overlap_chars = overlap * 4
        chunks = []
        i = 0
        while i < len(text):
            chunk = text[i : i + chunk_size]
            chunks.append(chunk)
            i += chunk_size - overlap_chars
        return chunks

def load_chunks_to_weaviate(
    chunks: List[str],
    collection_name: str,
    doc_id: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Load text chunks into Weaviate vector database.
    
    Args:
        chunks: List of text chunks to load
        collection_name: Name of the Weaviate collection
        doc_id: Unique document identifier
        description: Optional description for the collection
        
    Returns:
        Dictionary with success status, collection name, and chunks created
        
    Raises:
        RuntimeError: If Weaviate operations fail
    """
    try:
        # Ensure doc_id is JSON-serializable (UUID objects should be converted to strings)
        if doc_id is not None and not isinstance(doc_id, str):
            try:
                doc_id = str(doc_id)
            except Exception:
                doc_id = str(uuid.uuid4())

        # Initialize Weaviate connection
        weaviate_db = WeaviateDB()
        client = weaviate_db.client
        
        # Ensure collection exists
        if not client.collections.exists(collection_name):
            logger.info(f"Creating new collection: {collection_name}")
            weaviate_db.create_collection(
                name=collection_name,
                description=description or "Training data collection",
                properties=[
                    {"name": "text", "data_type": "text"},
                    {"name": "source", "data_type": "text"},
                    {"name": "chunk_index", "data_type": "int"},
                    {"name": "doc_id", "data_type": "text"},
                ],
                vectorizer="text2vec-openai"
            )
        
        chunks_count = len(chunks)
        logger.info(f"Loading {chunks_count} chunks into collection '{collection_name}'")
        
        # Get collection for batch insert
        collection = client.collections.get(collection_name)
        
        # Batch insert chunks into Weaviate
        logger.info("Inserting chunks into Weaviate...")
        with collection.batch.dynamic() as batch:
            for idx, chunk in enumerate(chunks):
                properties = {
                    "text": chunk,
                    "source": "agent_training_data",
                    "chunk_index": idx,
                    "doc_id": doc_id,
                }
                batch.add_object(properties=properties)
        
        logger.info(f"Successfully loaded {chunks_count} chunks into collection '{collection_name}'")
        
        return {
            "success": True,
            "chunks_created": chunks_count,
            "collection_name": collection_name,
            "doc_id": doc_id
        }
        
    except Exception as e:
        logger.error(f"Failed to load chunks to Weaviate: {str(e)}")
        raise RuntimeError(f"Failed to load chunks to Weaviate: {str(e)}")


def delete_chunks_from_weaviate(
    collection_name: str,
    doc_id: str
) -> Dict[str, Any]:
    """
    Delete all chunks with a specific doc_id from Weaviate collection.
    
    Args:
        collection_name: Name of the Weaviate collection
        doc_id: Unique document identifier to delete
        
    Returns:
        Dictionary with success status and number of chunks deleted
        
    Raises:
        RuntimeError: If Weaviate operations fail
        
    """
    try:
        # Initialize Weaviate connection
        weaviate_db = WeaviateDB()
        client = weaviate_db.client
        
        # Check if collection exists
        if not client.collections.exists(collection_name):
            logger.warning(f"Collection '{collection_name}' does not exist")
            return {
                "success": True,
                "chunks_deleted": 0,
                "message": f"Collection '{collection_name}' does not exist"
            }
        
        # Get collection
        collection = client.collections.get(collection_name)
        
        logger.info(f"Deleting chunks with doc_id '{doc_id}' from collection '{collection_name}'")
        
        # Delete all objects with matching doc_id
        result = collection.data.delete_many(
            where={
                "path": ["doc_id"],
                "operator": "Equal",
                "valueText": doc_id
            }
        )
        
        deleted_count = result.successful if hasattr(result, 'successful') else 0
        
        logger.info(f"Successfully deleted {deleted_count} chunks from collection '{collection_name}'")
        
        return {
            "success": True,
            "chunks_deleted": deleted_count,
            "collection_name": collection_name,
            "doc_id": doc_id
        }
        
    except Exception as e:
        logger.error(f"Failed to delete chunks from Weaviate: {str(e)}")
        raise RuntimeError(f"Failed to delete chunks from Weaviate: {str(e)}")


def load_data_with_tracking(
    scraped_content: str,
    collection_name: str,
    source_url: str,
    user_id: int,
    description: str = "",
    page_id: int = None
) -> Dict[str, Any]:
    """
    Load scraped web content into Weaviate with full database tracking.
    Similar to load_training_data_to_weaviate but for scraped web content.
    
    Creates a weaviate_data record, chunks the content, loads to Weaviate,
    and tracks status, statistics, and errors.
    
    Args:
        scraped_content: The scraped HTML/text content
        collection_name: Name of the Weaviate collection
        source_url: Source URL of the scraped content
        user_id: ID of the user loading the data
        description: Optional description
        page_id: Optional page ID to associate with the data
        
    Returns:
        Dictionary with success status, collection name, chunks created, doc_id, and db record ID
        
    Raises:
        ValueError: If scraped_content or collection_name is empty
        RuntimeError: If Weaviate operations fail
        
    """
    if not scraped_content.strip():
        raise ValueError("Scraped content cannot be empty")
    
    if not collection_name.strip():
        raise ValueError("Collection name cannot be empty")
    
    # Initialize PostgresDB
    db = PostgresDB()
    
    # Calculate statistics using helper function
    no_of_characters, no_of_lines, no_of_tokens = calculate_text_statistics(scraped_content)
    
    # Create database record with IN_PROGRESS status using helper function
    db_record = create_weaviate_data_record(
        db=db,
        collection_name=collection_name,
        description=description,
        content=scraped_content,
        no_of_characters=no_of_characters,
        no_of_lines=no_of_lines,
        no_of_tokens=no_of_tokens,
        user_id=user_id,
        page_id=page_id
    )
    
    record_id = db_record["id"]
    
    try:
        # Use a new UUID as document ID
        doc_id = str(uuid.uuid4())
        
        # Chunk the scraped content
        logger.info("Chunking scraped content...")
        chunks = chunk_text(scraped_content, max_tokens=400, overlap=50)
        chunks_count = len(chunks)
        
        logger.info(f"Created {chunks_count} chunks")
        
        # Load chunks to Weaviate
        weaviate_result = load_chunks_to_weaviate(
            chunks=chunks,
            collection_name=collection_name,
            doc_id=doc_id,
            description=description
        )
        
        chunks_count = weaviate_result["chunks_created"]
        logger.info(f"Successfully loaded {chunks_count} chunks into collection '{collection_name}'")
        
        # Prepare extra details for data_details JSON (page_id is now a proper column)
        extra_details = {
            "source_url": source_url
        }
        
        # Update database record with success using helper function
        update_weaviate_data_success(
            db=db,
            record_id=record_id,
            start_time=db_record["start_time"],
            doc_id=doc_id,
            chunks_created=chunks_count,
            description=description,
            extra_details=extra_details
        )
        
        return {
            "success": True,
            "message": "Data loaded successfully",
            "collection_name": collection_name,
            "chunks_created": chunks_count,
            "doc_id": doc_id,
            "source_url": source_url,
            "description": description,
            "record_id": record_id
        }
        
    except Exception as e:
        logger.error(f"Failed to load data to Weaviate: {str(e)}")
        
        # Update database record with error using helper function
        update_weaviate_data_error(
            db=db,
            record_id=record_id,
            error_msg=str(e),
            start_time=db_record["start_time"]
        )
        
        raise RuntimeError(f"Failed to load scraped data to Weaviate: {str(e)}")



def load_scraped_data_to_weaviate(
    scraped_content: str,
    collection_name: str,
    source_url: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Load scraped web content into Weaviate as a single document.
    This is a simple wrapper around load_chunks_to_weaviate for scraped content.
    Does NOT create database tracking records.
    
    For full tracking with weaviate_data records, use load_scraped_data_with_tracking().
    
    Args:
        scraped_content: The scraped HTML/text content
        collection_name: Name of the Weaviate collection
        source_url: Source URL of the scraped content (used as doc_id)
        description: Optional description
        
    Returns:
        Dictionary with success status, collection name, chunks created, and doc_id
        
    Raises:
        ValueError: If scraped_content or collection_name is empty
        RuntimeError: If Weaviate operations fail
        
    """
    if not scraped_content.strip():
        raise ValueError("Scraped content cannot be empty")
    
    if not collection_name.strip():
        raise ValueError("Collection name cannot be empty")
    
    try:
        # Chunk the scraped content
        logger.info(f"Chunking scraped content from {source_url}...")
        chunks = chunk_text(scraped_content, max_tokens=400, overlap=50)
        chunks_count = len(chunks)
        
        logger.info(f"Created {chunks_count} chunks from scraped content")
        
        # Load chunks to Weaviate using source_url as doc_id
        result = load_chunks_to_weaviate(
            chunks=chunks,
            collection_name=collection_name,
            doc_id=source_url,
            description=description or f"Scraped content from {source_url}"
        )
        
        logger.info(f"Successfully loaded {result['chunks_created']} chunks from {source_url}")
        
        return {
            "success": True,
            "collection_name": collection_name,
            "chunks_created": result["chunks_created"],
            "doc_id": source_url,
            "source_url": source_url
        }
        
    except Exception as e:
        logger.error(f"Failed to load scraped data to Weaviate: {str(e)}")
        raise RuntimeError(f"Failed to load scraped data to Weaviate: {str(e)}")


def create_weaviate_version_snapshot(
    weaviate_data_id: int,
    user_id: int,
    old_data: Dict[str, Any],
    new_data: Dict[str, Any],
    operation: str = "UPDATE",
    change_description: str = None
) -> Dict[str, Any]:
    """
    Create a version snapshot for a weaviate_data record using JSON diff.
    Helper function to create version history for weaviate_data updates.
    
    Args:
        weaviate_data_id: ID of the weaviate_data record
        user_id: ID of the user making the change
        old_data: Dictionary containing old values of the record
        new_data: Dictionary containing new values of the record
        operation: Type of operation (UPDATE, DELETE, RESTORE)
        change_description: Optional description of the change
        
    Returns:
        Dictionary with version creation status and version number
        
    """
    try:
        db = PostgresDB()
        
        # Create diff using the model's static method
        diff = WeaviateDataVersion.create_diff(old_data, new_data)
        
        # Only create version if there are actual changes
        if not WeaviateDataVersion.has_changes(diff):
            logger.info(f"No changes detected for record {weaviate_data_id}, skipping version creation")
            return {
                "success": True,
                "message": "No changes detected",
                "version_created": False
            }
        
        # Get the next version number
        version_query = text("""
            SELECT COALESCE(MAX(version_number), 0) + 1 as next_version
            FROM weaviate_data_versions
            WHERE weaviate_data_id = :weaviate_data_id
        """)
        
        with db.engine.connect() as conn:
            result = conn.execute(version_query, {"weaviate_data_id": weaviate_data_id})
            next_version = result.scalar()
        
        # Create version record
        insert_query = text("""
            INSERT INTO weaviate_data_versions (
                weaviate_data_id, version_number, changed_by, 
                change_description, old_values, new_values, diff, operation
            ) VALUES (
                :weaviate_data_id, :version_number, :changed_by,
                :change_description, CAST(:old_values AS jsonb), 
                CAST(:new_values AS jsonb), CAST(:diff AS jsonb), :operation
            ) RETURNING id
        """)
        
        with db.engine.begin() as conn:
            result = conn.execute(
                insert_query,
                {
                    "weaviate_data_id": weaviate_data_id,
                    "version_number": next_version,
                    "changed_by": user_id,
                    "change_description": change_description,
                    "old_values": json.dumps(old_data),
                    "new_values": json.dumps(new_data),
                    "diff": json.dumps(diff),
                    "operation": operation
                }
            )
            version_id = result.scalar()
        
        logger.info(f"Created version {next_version} for record {weaviate_data_id}")
        
        return {
            "success": True,
            "message": "Version snapshot created",
            "version_created": True,
            "version_id": version_id,
            "version_number": next_version,
            "changed_fields": WeaviateDataVersion.get_changed_fields(diff)
        }
        
    except Exception as e:
        logger.error(f"Error creating version snapshot: {str(e)}")
        raise RuntimeError(f"Failed to create version snapshot: {str(e)}")

