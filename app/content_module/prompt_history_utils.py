from typing import Optional, Dict, Any, Tuple
from content_module.content_responses import PromptHistoryResponse
from service_utils.db_utils.pg_db import PostgresDB
import uuid
from rag_module.rag import RagModule
from datetime import datetime, timezone


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
        "ai_response": None,  
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
    prompt_text: str,
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
    ai_response, _ = rag.generate_content(query=prompt_text) 

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

def get_prompt_histories(
        prompt_session_id: str,
        content_id: int
):
    db = PostgresDB()
        
    # Get all prompt history records for this session
    prompt_histories = db.read(
        "prompt_history",
        conditions={
            "prompt_session_id": prompt_session_id,
            "content_id": content_id,
            "deleted_on": None
        },
        order_by=[("created_on", True)]  # Ascending order (oldest first)
    )
    
    if not prompt_histories:
        return []
    
    # Convert to response models
    response_list = []

    print("PROMPT HISTORIES:", prompt_histories)

    for ph in prompt_histories:
        response_list.append(PromptHistoryResponse(
            id=ph["id"],
            prompt_session_id=ph["prompt_session_id"],
            content_id=ph["content_id"],
            user_prompt=ph["user_prompt"],
            ai_response=ph["ai_response"],
            prompt_type=ph["prompt_type"],
            created_on=ph["created_on"],
            deleted_on=ph["deleted_on"],
            prompt_action=ph["prompt_action"],
            updated_on=ph["updated_on"]
        ))
    
    return response_list


def update_prompt_action(
    id: int,
    prompt_action: str,
    prompt_name: Optional[str] = None,
    prompt_description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Placeholder function to save content as draft.
    Actual implementation would depend on application logic.
    """

    update_data = {
        "prompt_action": prompt_action,
        "prompt_name": prompt_name,
        "prompt_description": prompt_description,
        "updated_on": datetime.now(timezone.utc)
    }

    db = PostgresDB()

    updated_records = db.update(
        "prompt_history",
        data=update_data,
        conditions={"id": id}
    )

    if not updated_records or len(updated_records) == 0:
        raise Exception("Failed to update prompt history")

    return dict(updated_records[0]._mapping)


