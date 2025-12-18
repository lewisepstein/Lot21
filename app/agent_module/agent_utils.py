"""
Agent utility functions.
Business logic for agent-related operations including training data management.
"""
import json
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import text

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger
from weaviate_module.weaviate_utils import (
    chunk_text, 
    load_chunks_to_weaviate, 
    delete_chunks_from_weaviate,
    calculate_text_statistics,
    create_weaviate_data_record,
    update_weaviate_data_success,
    update_weaviate_data_error,
    create_weaviate_version_snapshot
)


# Set up logging
logger = get_logger(__name__)


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
    
    if not training_data.strip():
        raise ValueError("Training data cannot be empty")
    
    if not collection_name.strip():
        raise ValueError("Collection name cannot be empty")
    
    # Initialize PostgresDB
    db = PostgresDB()
    
    # Calculate statistics using helper function
    no_of_characters, no_of_lines, no_of_tokens = calculate_text_statistics(training_data)
    
    # Create database record with IN_PROGRESS status using helper function
    db_record = create_weaviate_data_record(
        db=db,
        collection_name=collection_name,
        description=description,
        content=training_data,
        no_of_characters=no_of_characters,
        no_of_lines=no_of_lines,
        no_of_tokens=no_of_tokens,
        user_id=user_id
    )
    
    record_id = db_record["id"]
    
    try:
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
        
        # Update database record with success using helper function
        update_weaviate_data_success(
            db=db,
            record_id=record_id,
            start_time=db_record["start_time"],
            doc_id=doc_id,
            chunks_created=chunks_count,
            description=description
        )
        
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
        
        # Update database record with error using helper function
        update_weaviate_data_error(
            db=db,
            record_id=record_id,
            error_msg=str(e),
            start_time=db_record["start_time"]
        )
        
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
        
        # Read weaviate_data records with version count using raw SQL
        query = text("""
            SELECT 
                w.*,
                COALESCE(MAX(v.version_number), 0) as current_version
            FROM weaviate_data w
            LEFT JOIN weaviate_data_versions v ON w.id = v.weaviate_data_id
            WHERE w.created_by = :user_id AND w.deleted_at IS NULL
            GROUP BY w.id
            ORDER BY w.id DESC
            LIMIT :limit
        """)
        
        with db.engine.connect() as conn:
            result = conn.execute(query, {"user_id": user_id, "limit": limit})
            records = [dict(row._mapping) for row in result]
        
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
                "updated_on": record.get("updated_on").isoformat() if record.get("updated_on") else None,
                "current_version": record.get("current_version", 0),
                "error_msg": record.get("error_msg")
            })
        
        return formatted_records
        
    except Exception as e:
        logger.error(f"Error fetching training history: {str(e)}")
        raise RuntimeError(f"Failed to fetch training history: {str(e)}")


def delete_training_record(record_id: int, user_id: int) -> Dict[str, Any]:
    """
    Delete a training record from both Weaviate and the database.
    Deletes chunks from Weaviate collection and soft-deletes the database record.
    
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
        records = db.read(
            "weaviate_data",
            conditions={"id": record_id, "created_by": user_id, "deleted_at": None}
        )
        
        if not records or len(records) == 0:
            raise ValueError("Training record not found")
        
        record = records[0]
        collection_name = record.get("collection_name")
        data_details = record.get("data_details") or {}
        doc_id = data_details.get("doc_id")
        
        # Store old values for version control before deletion
        old_values = {
            "content": record.get("content"),
            "description": record.get("description"),
            "no_of_lines": record.get("no_of_lines"),
            "no_of_tokens": record.get("no_of_tokens"),
            "no_of_characters": record.get("no_of_characters"),
            "data_details": record.get("data_details"),
            "deleted_at": None
        }
        
        # Delete from Weaviate if doc_id exists
        weaviate_deleted = 0
        if doc_id and collection_name:
            try:
                logger.info(f"Deleting chunks from Weaviate: collection='{collection_name}', doc_id='{doc_id}'")
                weaviate_result = delete_chunks_from_weaviate(
                    collection_name=collection_name,
                    doc_id=doc_id
                )
                weaviate_deleted = weaviate_result.get("chunks_deleted", 0)
                logger.info(f"Deleted {weaviate_deleted} chunks from Weaviate")
            except Exception as weaviate_error:
                logger.error(f"Error deleting from Weaviate: {str(weaviate_error)}")
                # Continue with database deletion even if Weaviate deletion fails
        else:
            logger.warning(f"No doc_id or collection_name found for record {record_id}, skipping Weaviate deletion")
        
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
        
        # Create version snapshot for deletion
        new_values = {**old_values, "deleted_at": now.isoformat()}
        
        try:
            version_result = create_weaviate_version_snapshot(
                weaviate_data_id=record_id,
                user_id=user_id,
                old_data=old_values,
                new_data=new_values,
                operation="DELETE",
                change_description="Training data deleted"
            )
            logger.info(f"Version snapshot created for deletion: {version_result}")
        except Exception as version_error:
            # Log error but don't fail the deletion
            logger.error(f"Failed to create version snapshot: {str(version_error)}")
        
        return {
            "success": True,
            "message": "Training record deleted successfully",
            "chunks_deleted_from_weaviate": weaviate_deleted
        }
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error deleting training record: {str(e)}")
        raise RuntimeError(f"Failed to delete training record: {str(e)}")


def update_training_record(
    record_id: int,
    user_id: int,
    training_data: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Update an existing training record with new data.
    Deletes old chunks from Weaviate and loads new chunks.
    
    Args:
        record_id: ID of the record to update
        user_id: ID of the user performing the update
        training_data: New training data content
        description: Updated description
        
    Returns:
        Dictionary with success status and updated information
        
    Raises:
        ValueError: If record not found, data is empty, or doesn't belong to user
        RuntimeError: If update operation fails
        
    Examples:
        >>> result = update_training_record(
        ...     record_id=1,
        ...     user_id=1,
        ...     training_data="Updated content...",
        ...     description="Updated description"
        ... )
    """
    import uuid
    import tiktoken
    
    ENCODING = "cl100k_base"
    
    if not training_data.strip():
        raise ValueError("Training data cannot be empty")
    
    try:
        db = PostgresDB()
        
        # Check if record exists and belongs to user
        records = db.read(
            "weaviate_data",
            conditions={"id": record_id, "created_by": user_id, "deleted_at": None}
        )
        
        if not records or len(records) == 0:
            raise ValueError("Training record not found")
        
        old_record = records[0]
        collection_name = old_record.get("collection_name")
        old_data_details = old_record.get("data_details") or {}
        old_doc_id = old_data_details.get("doc_id")
        
        # Store old values for version control
        old_values = {
            "content": old_record.get("content"),
            "description": old_record.get("description"),
            "no_of_lines": old_record.get("no_of_lines"),
            "no_of_tokens": old_record.get("no_of_tokens"),
            "no_of_characters": old_record.get("no_of_characters"),
            "data_details": old_record.get("data_details")
        }
        
        # Calculate new statistics
        no_of_characters = len(training_data)
        no_of_lines = len(training_data.split('\n'))
        
        try:
            enc = tiktoken.get_encoding(ENCODING)
            no_of_tokens = len(enc.encode(training_data))
        except Exception as e:
            logger.warning(f"Failed to calculate tokens: {e}")
            no_of_tokens = None
        
        # Delete old chunks from Weaviate
        if old_doc_id and collection_name:
            try:
                logger.info(f"Deleting old chunks from Weaviate: doc_id='{old_doc_id}'")
                delete_result = delete_chunks_from_weaviate(
                    collection_name=collection_name,
                    doc_id=old_doc_id
                )
                logger.info(f"Deleted {delete_result.get('chunks_deleted', 0)} old chunks")
            except Exception as weaviate_error:
                logger.error(f"Error deleting old chunks: {str(weaviate_error)}")
                # Continue with update even if deletion fails
        
        # Generate new document ID
        new_doc_id = str(uuid.uuid4())
        
        # Chunk the new training data
        logger.info("Chunking new training data...")
        chunks = chunk_text(training_data, max_tokens=400, overlap=50)
        chunks_count = len(chunks)
        
        logger.info(f"Created {chunks_count} new chunks")
        
        # Load new chunks to Weaviate
        start_time = datetime.now(datetime.now().astimezone().tzinfo)
        
        load_chunks_to_weaviate(
            chunks=chunks,
            collection_name=collection_name,
            doc_id=new_doc_id,
            description=description
        )
        
        end_time = datetime.now(datetime.now().astimezone().tzinfo)
        processing_duration = int((end_time - start_time).total_seconds())
        
        # Update database record
        data_details_json = json.dumps({
            "doc_id": new_doc_id,
            "chunks_created": chunks_count,
            "collection_description": description
        })
        
        now = datetime.now(datetime.now().astimezone().tzinfo)
        
        query = text("""
            UPDATE weaviate_data 
            SET content = :content,
                description = :description,
                no_of_lines = :no_of_lines,
                no_of_tokens = :no_of_tokens,
                no_of_characters = :no_of_characters,
                data_details = CAST(:data_details AS jsonb),
                processing_duration = :processing_duration,
                updated_on = :updated_on,
                error_msg = NULL
            WHERE id = :id AND created_by = :user_id
        """)
        
        with db.engine.begin() as conn:
            conn.execute(
                query,
                {
                    "content": training_data,
                    "description": description,
                    "no_of_lines": no_of_lines,
                    "no_of_tokens": no_of_tokens,
                    "no_of_characters": no_of_characters,
                    "data_details": data_details_json,
                    "processing_duration": processing_duration,
                    "updated_on": now,
                    "id": record_id,
                    "user_id": user_id
                }
            )
        
        logger.info(f"Updated training record {record_id} for user {user_id}")
        
        # Create version snapshot with new values
        new_values = {
            "content": training_data,
            "description": description,
            "no_of_lines": no_of_lines,
            "no_of_tokens": no_of_tokens,
            "no_of_characters": no_of_characters,
            "data_details": json.loads(data_details_json)
        }
        
        try:
            version_result = create_weaviate_version_snapshot(
                weaviate_data_id=record_id,
                user_id=user_id,
                old_data=old_values,
                new_data=new_values,
                operation="UPDATE",
                change_description="Training data updated"
            )
            logger.info(f"Version snapshot created: {version_result}")
        except Exception as version_error:
            # Log error but don't fail the update
            logger.error(f"Failed to create version snapshot: {str(version_error)}")
        
        return {
            "success": True,
            "message": "Training record updated successfully",
            "record_id": record_id,
            "chunks_created": chunks_count,
            "doc_id": new_doc_id
        }
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error updating training record: {str(e)}")
        raise RuntimeError(f"Failed to update training record: {str(e)}")


def get_version_history(
    weaviate_data_id: int,
    user_id: int = None
) -> List[Dict[str, Any]]:
    """
    Get version history for a weaviate_data record.
    
    Args:
        weaviate_data_id: ID of the weaviate_data record
        user_id: Optional user ID to filter by user access
        
    Returns:
        List of version records sorted by version number (newest first)
        
    Examples:
        >>> history = get_version_history(weaviate_data_id=1)
    """
    try:
        db = PostgresDB()
        
        # Check if user has access to this record
        if user_id:
            access_query = text("""
                SELECT 1 FROM weaviate_data 
                WHERE id = :weaviate_data_id AND created_by = :user_id
            """)
            
            with db.engine.connect() as conn:
                result = conn.execute(
                    access_query,
                    {"weaviate_data_id": weaviate_data_id, "user_id": user_id}
                )
                if not result.scalar():
                    raise ValueError("Access denied or record not found")
        
        # Get version history
        history_query = text("""
            SELECT 
                v.id, v.weaviate_data_id, v.version_number, v.changed_by,
                v.changed_at, v.change_description, v.old_values, v.new_values,
                v.diff, v.operation,
                u.email as changed_by_email
            FROM weaviate_data_versions v
            LEFT JOIN users u ON v.changed_by = u.id
            WHERE v.weaviate_data_id = :weaviate_data_id
            ORDER BY v.version_number DESC
        """)
        
        with db.engine.connect() as conn:
            result = conn.execute(history_query, {"weaviate_data_id": weaviate_data_id})
            versions = []
            
            for row in result:
                versions.append({
                    "id": row.id,
                    "weaviate_data_id": row.weaviate_data_id,
                    "version_number": row.version_number,
                    "changed_by": row.changed_by,
                    "changed_by_email": row.changed_by_email,
                    "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                    "change_description": row.change_description,
                    "old_values": row.old_values,
                    "new_values": row.new_values,
                    "diff": row.diff,
                    "operation": row.operation
                })
        
        logger.info(f"Retrieved {len(versions)} versions for record {weaviate_data_id}")
        return versions
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error retrieving version history: {str(e)}")
        raise RuntimeError(f"Failed to retrieve version history: {str(e)}")


def restore_from_version(
    weaviate_data_id: int,
    version_number: int,
    user_id: int
) -> Dict[str, Any]:
    """
    Restore a weaviate_data record to a previous version.
    
    Args:
        weaviate_data_id: ID of the weaviate_data record
        version_number: Version number to restore to
        user_id: ID of the user performing the restore
        
    Returns:
        Dictionary with restore status and updated record info
        
    Examples:
        >>> result = restore_from_version(
        ...     weaviate_data_id=1,
        ...     version_number=2,
        ...     user_id=1
        ... )
    """
    try:
        db = PostgresDB()
        
        # Get the version to restore
        version_query = text("""
            SELECT old_values, new_values
            FROM weaviate_data_versions
            WHERE weaviate_data_id = :weaviate_data_id 
            AND version_number = :version_number
        """)
        
        with db.engine.connect() as conn:
            result = conn.execute(
                version_query,
                {"weaviate_data_id": weaviate_data_id, "version_number": version_number}
            )
            row = result.fetchone()
            
            if not row:
                raise ValueError(f"Version {version_number} not found for record {weaviate_data_id}")
        
        # Get old values from the version (these are the values to restore to)
        restore_data = row.old_values
        
        # Get current record data for version snapshot
        current_records = db.read(
            "weaviate_data",
            conditions={"id": weaviate_data_id, "created_by": user_id}
        )
        
        if not current_records:
            raise ValueError("Record not found or access denied")
        
        current_record = current_records[0]
        
        # Create version snapshot before restore
        old_data = {
            "content": current_record.get("content"),
            "description": current_record.get("description"),
            "no_of_lines": current_record.get("no_of_lines"),
            "no_of_tokens": current_record.get("no_of_tokens"),
            "no_of_characters": current_record.get("no_of_characters")
        }
        
        new_data = {
            "content": restore_data.get("content"),
            "description": restore_data.get("description"),
            "no_of_lines": restore_data.get("no_of_lines"),
            "no_of_tokens": restore_data.get("no_of_tokens"),
            "no_of_characters": restore_data.get("no_of_characters")
        }
        
        create_weaviate_version_snapshot(
            weaviate_data_id=weaviate_data_id,
            user_id=user_id,
            old_data=old_data,
            new_data=new_data,
            operation="RESTORE",
            change_description=f"Restored to version {version_number}"
        )
        
        # Update the record using the update_training_record function
        result = update_training_record(
            record_id=weaviate_data_id,
            user_id=user_id,
            training_data=restore_data.get("content", ""),
            description=restore_data.get("description", "")
        )
        
        return {
            "success": True,
            "message": f"Successfully restored to version {version_number}",
            "restored_version": version_number,
            **result
        }
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error restoring from version: {str(e)}")
        raise RuntimeError(f"Failed to restore from version: {str(e)}")

