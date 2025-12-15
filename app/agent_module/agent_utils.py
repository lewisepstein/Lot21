"""
Agent utility functions.
Business logic for agent-related operations including training data management.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import text

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.db_utils.weaviate_db import WeaviateDB
from weaviate_module.weaviate_utils import chunk_text, load_chunks_to_weaviate
from models.weaviate_data import WeaviateDataStatusEnum

# Set up logging
logger = logging.getLogger(__name__)


def load_training_data_to_weaviate(
    training_data: str,
    collection_name: str,
    user_id: int,
    description: str = ""
) -> Dict[str, Any]:
    """
    Load training data into Weaviate vector database and store metadata in database.
    Chunks the data and stores it with metadata.
    
    Args:
        training_data: The text data to load
        collection_name: Name of the Weaviate collection
        user_id: ID of the user loading the data
        description: Optional description for the collection
        
    Returns:
        Dictionary with success status, collection name, chunks created, doc_id, and db record ID
        
    Raises:
        ValueError: If training data or collection name is empty
        RuntimeError: If Weaviate operations fail
        
    Examples:
        >>> result = load_training_data_to_weaviate(
        ...     "Long text data...",
        ...     "my_collection",
        ...     user_id=1,
        ...     description="Training data for AI model"
        ... )
        >>> print(f"Loaded {result['chunks_created']} chunks")
    """
    import uuid
    import tiktoken
    
    ENCODING = "cl100k_base"
    
    if not training_data.strip():
        raise ValueError("Training data cannot be empty")
    
    if not collection_name.strip():
        raise ValueError("Collection name cannot be empty")
    
    # Calculate statistics
    no_of_characters = len(training_data)
    no_of_lines = len(training_data.split('\n'))
    
    # Calculate tokens
    try:
        enc = tiktoken.get_encoding(ENCODING)
        no_of_tokens = len(enc.encode(training_data))
    except Exception as e:
        logger.warning(f"Failed to calculate tokens: {e}")
        no_of_tokens = None
    
    # Initialize PostgresDB
    db = PostgresDB()
    
    # Get current time for tracking
    start_time = datetime.now(datetime.now().astimezone().tzinfo)
    
    # Create database record with IN_PROGRESS status
    weaviate_data_dict = {
        "collection_name": collection_name,
        "description": description,
        "content": training_data,
        "status": WeaviateDataStatusEnum.IN_PROGRESS.value,
        "no_of_lines": no_of_lines,
        "no_of_tokens": no_of_tokens,
        "no_of_characters": no_of_characters,
        "created_by": user_id
    }
    
    try:
        # Create new weaviate_data entry
        db_record = db.create("weaviate_data", weaviate_data_dict)
        
        if not db_record:
            raise Exception("Failed to create weaviate_data record")
        
        record_id = db_record["id"]
        
        # Update with start_time using raw SQL to avoid validation issues
        with db.engine.begin() as conn:
            conn.execute(
                text("UPDATE weaviate_data SET start_time = :start_time WHERE id = :id"),
                {"start_time": start_time, "id": record_id}
            )
        db_record["start_time"] = start_time
        
        logger.info(f"Created weaviate_data record with ID: {record_id}")
        logger.info(f"Loading training data into collection: {collection_name}")
        
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        
        # Chunk the training data
        logger.info("Chunking training data...")
        chunks = chunk_text(training_data, max_tokens=400, overlap=50)
        chunks_count = len(chunks)
        
        logger.info(f"Created {chunks_count} chunks")
        
        # Load chunks to Weaviate using pure Weaviate utility function
        weaviate_result = load_chunks_to_weaviate(
            chunks=chunks,
            collection_name=collection_name,
            doc_id=doc_id,
            description=description
        )
        
        chunks_count = weaviate_result["chunks_created"]
        logger.info(f"Successfully loaded {chunks_count} chunks into collection '{collection_name}'")
        
        # Calculate processing duration
        end_time = datetime.now(datetime.now().astimezone().tzinfo)
        start_time = db_record["start_time"]
        processing_duration = int((end_time - start_time).total_seconds())
        
        # Update database record with success using raw SQL to avoid validation issues
        data_details_json = json.dumps({
            "doc_id": doc_id,
            "chunks_created": chunks_count,
            "collection_description": description
        })
        
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
        
        return {
            "success": True,
            "message": "Training data loaded successfully",
            "collection_name": collection_name,
            "chunks_created": chunks_count,
            "doc_id": doc_id,
            "description": description,
            "record_id": record_id
        }
        
    except Exception as e:
        logger.error(f"Failed to load data to Weaviate: {str(e)}")
        
        # Update database record with error
        try:
            end_time = datetime.now(datetime.now().astimezone().tzinfo)
            # Check if db_record was created
            if 'db_record' in locals() and db_record:
                start_time = db_record.get("start_time", end_time)
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
                            "error_msg": str(e),
                            "id": db_record["id"]
                        }
                    )
                logger.info(f"Updated weaviate_data record {db_record['id']} with ERROR status")
        except Exception as db_error:
            logger.error(f"Failed to update database record: {str(db_error)}")
        
        raise RuntimeError(f"Failed to load data to Weaviate: {str(e)}")


def get_training_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get training data loading history from weaviate_data table.
    
    Args:
        user_id: ID of the user to fetch history for
        limit: Maximum number of records to return (default: 50)
        
    Returns:
        List of formatted training history records
        
    Examples:
        >>> history = get_training_history(user_id=1, limit=20)
        >>> print(f"Found {len(history)} records")
    """
    try:
        db = PostgresDB()
        
        # Read weaviate_data records ordered by id desc
        records = db.read(
            "weaviate_data",
            conditions={"created_by": user_id, "deleted_at": None},
            order_by=[("id", False)],  # False means descending
            limit=limit
        )
        
        # Format the records for frontend
        formatted_records = []
        for record in records:
            # Calculate duration_formatted
            duration_formatted = None
            if record.get("processing_duration") is not None:
                duration = record.get("processing_duration")
                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    duration_formatted = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    duration_formatted = f"{minutes}m {seconds}s"
                else:
                    duration_formatted = f"{seconds}s"
            
            # Extract no_of_chunks from data_details if available
            data_details = record.get("data_details") or {}
            no_of_chunks = data_details.get("chunks_created", 0)
            
            formatted_records.append({
                "id": record.get("id"),
                "collection_name": record.get("collection_name"),
                "description": record.get("description"),
                "content": record.get("content"),
                "data_details": data_details,  
                "status": record.get("status"),
                "no_of_lines": record.get("no_of_lines"),
                "no_of_tokens": record.get("no_of_tokens"),
                "no_of_characters": record.get("no_of_characters"),
                "no_of_chunks": no_of_chunks,
                "processing_duration": record.get("processing_duration"),
                "duration_formatted": duration_formatted,
                "start_time": record.get("start_time").isoformat() if record.get("start_time") else None,
                "end_time": record.get("end_time").isoformat() if record.get("end_time") else None,
                "created_at": record.get("created_at").isoformat() if record.get("created_at") else None,
                "error_msg": record.get("error_msg")
            })
        
        return formatted_records
        
    except Exception as e:
        logger.error(f"Error fetching training history: {str(e)}")
        raise RuntimeError(f"Failed to fetch training history: {str(e)}")


def delete_training_record(record_id: int, user_id: int) -> Dict[str, Any]:
    """
    Soft delete a training record from the database.
    
    Args:
        record_id: ID of the record to delete
        user_id: ID of the user performing the deletion
        
    Returns:
        Dictionary with success status and message
        
    Raises:
        ValueError: If record not found or doesn't belong to user
        RuntimeError: If database operation fails
        
    Examples:
        >>> result = delete_training_record(record_id=1, user_id=1)
        >>> print(result['message'])
    """
    try:
        db = PostgresDB()
        
        # First check if record exists and belongs to user
        record = db.read(
            "weaviate_data",
            conditions={"id": record_id, "created_by": user_id, "deleted_at": None}
        )
        
        if not record or len(record) == 0:
            raise ValueError("Training record not found")
        
        # Soft delete the record using raw SQL
        now = datetime.now(datetime.now().astimezone().tzinfo)
        
        query = text("""
            UPDATE weaviate_data 
            SET deleted_at = :deleted_at 
            WHERE id = :id AND created_by = :user_id
        """)
        
        with db.engine.begin() as conn:
            conn.execute(
                query,
                {
                    "deleted_at": now,
                    "id": record_id,
                    "user_id": user_id
                }
            )
        
        logger.info(f"Soft deleted training record {record_id} for user {user_id}")
        
        return {
            "success": True,
            "message": "Training record deleted successfully"
        }
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error deleting training record: {str(e)}")
        raise RuntimeError(f"Failed to delete training record: {str(e)}")
