from typing import Optional, Dict, Any, List
from service_utils.db_utils.pg_db import PostgresDB
from models.content import ContentActionEnum, ContentApprovalStatusEnum


def get_latest_content(category_id: int) -> Optional[Dict[str, Any]]:
    """
    Get the latest content record for a given category.
    
    Args:
        category_id: ID of the category to fetch content for
    
    Returns:
        Dictionary containing the latest content record, or None if not found
    """
    db = PostgresDB()
    
    # Read content for the given category, ordered by created_on descending
    # order_by expects list of tuples: [(column_name, is_ascending)]
    contents = db.read(
        "content",
        conditions={"category_id": category_id, "deleted_on": None},
        order_by=[("created_on", False)],  # False means descending order
        limit=1
    )
    
    if not contents or len(contents) == 0:
        return None
    
    return contents[0]

def get_unattached_content() -> Optional[List[Dict[str, Any]]]:
    """
    Get content records that are not attached to any page.
    """

    EXCLUDED_FIELDS = {
        "id",
        "created_at",
        "updated_on",
        "deleted_at",
        "page_id",
        "content_id",
        "start_time",
        "end_time",
        "error_msg",
        "data_details"
    }

    db = PostgresDB()

    contents = db.read(
        "weaviate_data",
        conditions={"page_id": None, "deleted_on": None},
        order_by=[("created_on", False)]
    )

    if not contents:
        return None

    serialized_data: List[Dict[str, Any]] = []

    for content in contents:
        item = dict(content)

        # Build filtered data in ONE pass
        item["data"] = {
            k: v
            for k, v in item.items()
            if k not in EXCLUDED_FIELDS
        }

        # Remove fields not needed at top-level
        for field in ("error_msg",):
            item.pop(field, None)

        serialized_data.append(item)

    return serialized_data


def create_content_record(
    category_id: int,
    prompt_data: Optional[str],
    action: Optional[ContentActionEnum],
    user_id: int,
    content_type: Optional[str] = None,
    page_id: Optional[int] = None,
    generated_content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new content record in the database.
    
    Args:
        category_id: ID of the category
        prompt_data: User's prompt text (can be None)
        action: Content action enum (NEW, DRAFT, etc.)
        user_id: ID of the user creating the content
        content_type: Type of content (UNDERSTANDING, PROJECTS, etc.)
    
    Returns:
        Dictionary containing the created content record
        
    Raises:
        Exception: If database insert fails
    """
    db = PostgresDB()
    
    # Determine action - use provided action or default to DRAFT
    action_value = action.value if action else ContentActionEnum.DRAFT.value
    
    # Prepare content data for insertion
    content_dict = {
        "category_id": category_id,
        "prompt_data": prompt_data,
        "action": action_value,
        "approval_status": ContentApprovalStatusEnum.PENDING.value,
        "created_by": user_id,
        "page_id": page_id,
        "generated_content": generated_content
    }
    
    # Add content_type if provided
    if content_type:
        content_dict["content_type"] = content_type
    
    # Create new content entry
    new_content = db.create("content", content_dict)
    
    if not new_content:
        raise Exception("Failed to create content")
    
    return new_content

