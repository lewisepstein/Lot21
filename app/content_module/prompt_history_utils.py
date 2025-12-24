from typing import Optional, Dict, Any, Tuple
from service_utils.db_utils.pg_db import PostgresDB
import uuid
from rag_module.rag import RagModule


def create_prompt_history_record(
    content_id: int,
    prompt_data: Optional[str],
    prompt_session_id: Optional[str] = None
) -> Tuple[Dict[str, Any], str, int]:
    """
    Create a new prompt_history record with a UUID session ID.
    
    Args:
        content_id: ID of the content record
        prompt_data: User's prompt text
    
    Returns:
        Tuple of (prompt_history_dict, prompt_session_id, prompt_history_id)
        
    Raises:
        Exception: If database insert fails
    """
    db = PostgresDB()
    
    # Generate UUID for prompt session
    prompt_session_id = str(uuid.uuid4())
    
    # Create prompt_history entry
    prompt_history_dict = {
        "prompt_session_id": prompt_session_id,
        "content_id": content_id,
        "user_prompt": prompt_data,
        "ai_response": None,  # Will be populated later
        "prompt_type": "TEXT",  # Default to TEXT
        "prompt_action": "NEW"  # Default to NEW
    }
    
    prompt_history = db.create("prompt_history", prompt_history_dict)

    if not prompt_history:
        raise Exception("Failed to create prompt history")
        
    return prompt_history, prompt_session_id, prompt_history["id"]


def add_draft_to_prompt_history(
    prompt_session_id: str,
    content_id: int,
    prompt_text: str
) -> Dict[str, Any]:
    """
    Add a draft prompt to an existing prompt history session.
    If a record exists with prompt_action='NEW' and null user_prompt, update it.
    Otherwise, create a new record.
    
    Args:
        prompt_session_id: Existing UUID session ID to add the draft to
        content_id: ID of the content record
        prompt_text: User's prompt text for this draft
    
    Returns:
        Dictionary containing the created or updated prompt_history record
        
    Raises:
        Exception: If database operation fails
    """
    db = PostgresDB()
    
    # Check for existing record with prompt_action='NEW' and null user_prompt
    existing_records = db.read(
        "prompt_history",
        conditions={
            "prompt_session_id": prompt_session_id,
            "content_id": content_id,
            "prompt_action": "NEW",
            "user_prompt": None,
            "deleted_on": None
        }
    )

    # Retrieve context for the draft prompt (not used here but could be logged or processed)
    rag = RagModule()
    ai_response = rag.generate_content(query=prompt_text) 

    print("AI RESPONSE FOR DRAFT:", ai_response)
    
    if existing_records and len(existing_records) > 0:
        # Update the existing record
        existing_record = existing_records[0]
        update_data = {
            "user_prompt": prompt_text,
            "prompt_action": "DRAFT",
            "ai_response": ai_response
        }
        
        updated_records = db.update(
            "prompt_history",
            data=update_data,
            conditions={"id": existing_record["id"]}
        )
        
        if not updated_records or len(updated_records) == 0:
            raise Exception("Failed to update prompt history")
        
        return dict(updated_records[0]._mapping)
    else:
        # Create new prompt_history entry with existing session_id
        prompt_history_dict = {
            "prompt_session_id": prompt_session_id,
            "content_id": content_id,
            "user_prompt": prompt_text,
            "ai_response": ai_response,
            "prompt_type": "TEXT",
            "prompt_action": "DRAFT"  # Default to DRAFT for drafts
        }
        
        prompt_history = db.create("prompt_history", prompt_history_dict)
        
        if not prompt_history:
            raise Exception("Failed to create prompt history")
        
        return prompt_history
