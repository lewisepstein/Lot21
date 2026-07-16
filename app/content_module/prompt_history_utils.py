from typing import Optional, Dict, Any, Tuple, List
from content_module.content_responses import PromptHistoryResponse
from service_utils.db_utils.pg_db import PostgresDB
import re
import uuid
from rag_module.rag import RagModule
from datetime import datetime, timezone
from service_utils.aws_services import safe_upload_image_to_s3, upload_base64_image_to_s3
import json

from service_utils.log_management import get_logger
from weaviate_module.weaviate_utils import (
    chunk_text,
    load_chunks_to_weaviate,
    delete_chunks_from_weaviate,
)

logger = get_logger(__name__)


def _extract_response_text(raw: Any) -> str:
    """ai_response is stored as JSON like {"text": ..., "images": ...} or plain text."""
    text = str(raw or "").strip()
    if text.startswith("{"):
        try:
            text = (json.loads(text).get("text") or "").strip()
        except (ValueError, TypeError):
            pass
    return text


# Project titles appear in three shapes across generated content:
# a standalone title line right above the year line ("POWERHOUSE TELEMARK"
# then "2020 - BREEAM OUTSTANDING"), an explicit "PROJECT X" header, or a
# numbered list item ("3. GreenSteel — ...").
_TITLE_LINE_RE = re.compile(r"^[A-Z0-9][A-Za-z0-9+&'’. -]{2,60}$")
_YEAR_LINE_RE = re.compile(r"^\s*(19|20)\d{2}\b")
_PROJECT_HEADER_RE = re.compile(r"(?im)^PROJECT\s+([A-Z0-9][A-Za-z0-9+&'’. -]{2,60})\s*$")
_NUMBERED_ITEM_RE = re.compile(
    r"(?m)^\s*\d+\.\s*(?:Project\s+)?([A-Z][A-Za-z0-9+&'’. -]{2,60}?)\s*(?:[—–:-]|$)"
)


def _extract_project_names(text: str) -> List[str]:
    """Project names mentioned in one generated response (deterministic, no AI)."""
    if not text:
        return []
    names = []
    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        if not _TITLE_LINE_RE.match(line):
            continue
        if line.upper().startswith("PROJECT "):
            continue  # the PROJECT-header regex captures these without the prefix
        # the title line is the one directly above the year/status line
        for nxt in lines[i + 1 : i + 3]:
            if not nxt:
                continue
            if _YEAR_LINE_RE.match(nxt):
                names.append(line)
            break
    names.extend(m.group(1) for m in _PROJECT_HEADER_RE.finditer(text))
    names.extend(m.group(1) for m in _NUMBERED_ITEM_RE.finditer(text))
    unique = []
    seen = set()
    for name in names:
        cleaned = " ".join(name.split()).strip(".- ")
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique


def _get_seen_project_names(
    db: PostgresDB, content_id: Optional[int], max_names: int = 60
) -> Optional[List[str]]:
    """
    Project names from ALL earlier generations for this page (every session) —
    passed to generation so new drafts surface fresh projects instead of
    repeating ones the user has already seen.
    """
    if not content_id:
        return None
    try:
        rows = db.read(
            "prompt_history",
            conditions={"content_id": content_id, "deleted_on": None},
            columns=["ai_response"],
            order_by=[("created_on", False)],
            limit=40,
        )
        names = []
        seen = set()
        for row in rows or []:  # newest first, so recent names win the cap
            text = _extract_response_text(row.get("ai_response"))
            for name in _extract_project_names(text):
                key = name.casefold()
                if key not in seen:
                    seen.add(key)
                    names.append(name)
            if len(names) >= max_names:
                break
        return names[:max_names] or None
    except Exception as e:
        logger.warning(f"Could not load seen projects for content {content_id}: {e}")
        return None


def _get_conversation_history(
    db: PostgresDB, prompt_session_id: Optional[str], limit: int = 4
):
    """
    Last few completed exchanges of this prompt session (oldest first) —
    passed to generation so follow-ups like "add X to project 3" build on
    the previous response instead of being refused as out of scope.
    """
    if not prompt_session_id:
        return None
    try:
        rows = db.read(
            "prompt_history",
            conditions={"prompt_session_id": prompt_session_id, "deleted_on": None},
            order_by=[("created_on", False)],
            limit=limit * 2,  # some rows are placeholders without a response yet
        )
        # Refusal/error responses are not content — building a follow-up on
        # top of them would carry the failure forward
        skip_markers = (
            "outside the scope of the provided context",
            "i am sorry, but as a lot21 specialist",
            "we're having trouble reaching the ai agent",
            "unable to connect to the ai service",
        )
        turns = []
        for row in rows or []:  # newest first
            user_prompt = (row.get("user_prompt") or "").strip()
            response_text = _extract_response_text(row.get("ai_response"))
            if not user_prompt or not response_text:
                continue
            if any(m in response_text.lower() for m in skip_markers):
                continue
            turns.append(
                {"prompt": user_prompt[:1000], "response": response_text[:4000]}
            )
            if len(turns) >= limit:
                break
        turns.reverse()  # oldest first for the model
        return turns or None
    except Exception as e:
        logger.warning(
            f"Could not load conversation history for session {prompt_session_id}: {e}"
        )
        return None


def _get_page_sub_category(db: PostgresDB, content_id: Optional[int]) -> Optional[str]:
    """The page's saved climate pillar (ADAPT/MITIGATE/RESTORE), if configured."""
    if not content_id:
        return None
    try:
        contents = db.read(
            "content",
            conditions={"id": content_id, "deleted_on": None},
            columns=["page_id"],
            limit=1,
        )
        page_id = contents[0].get("page_id") if contents else None
        if not page_id:
            return None
        pages = db.read(
            "pages",
            conditions={"id": page_id, "deleted_on": None},
            columns=["sub_category"],
            limit=1,
        )
        return pages[0].get("sub_category") if pages else None
    except Exception as e:
        logger.warning(f"Could not read page sub_category for content {content_id}: {e}")
        return None


def _get_rejected_feedback(db: PostgresDB, content_id: Optional[int], limit: int = 3):
    """
    Recent rejected drafts for this content — passed to generation so the next
    draft avoids what the user already turned down.
    """
    if not content_id:
        return None
    try:
        rows = db.read(
            "prompt_history",
            conditions={
                "content_id": content_id,
                "prompt_action": "REJECTED",
                "deleted_on": None,
            },
            order_by=[("updated_on", False)],
            limit=limit,
        )
        items = []
        for row in rows or []:
            text = _extract_response_text(row.get("ai_response"))
            if not text:
                continue
            items.append({
                "text": text[:400],
                "note": (row.get("prompt_description") or "").strip(),
            })
        return items or None
    except Exception as e:
        logger.warning(f"Could not load rejected feedback for content {content_id}: {e}")
        return None


def _sync_approval_training_data(record: Dict[str, Any]):
    """
    Approval is a training signal: approved responses are ingested into
    Weaviate as high-quality training data; rejecting withdraws them.
    """
    action = record.get("prompt_action")
    action = action.value if hasattr(action, "value") else action
    doc_id = f"approved_prompt_{record['id']}"

    if action == "APPROVED":
        text = _extract_response_text(record.get("ai_response"))
        if not text:
            return
        # re-approval replaces instead of duplicating
        delete_chunks_from_weaviate("training_data", doc_id)
        chunks = chunk_text(text)
        load_chunks_to_weaviate(
            chunks,
            "training_data",
            doc_id,
            description="User-approved content",
            source="approved_content",
        )
        logger.info(f"Approved response {record['id']} ingested as training data ({len(chunks)} chunks)")
    elif action == "REJECTED":
        delete_chunks_from_weaviate("training_data", doc_id)


def add_attachments_to_prompt_history(db: PostgresDB, prompt_history_id: int, img: str):

    try:
        file_path = safe_upload_image_to_s3(img, prefix="attachments")

        add_attachments_data = {
            "prompt_history_id": prompt_history_id,
            "attachments_data": file_path,
            "generated_images": None,
            "status": "NEW"
        }
        db.create("prompt_attachments", add_attachments_data)
    except Exception as e:
        raise Exception(f"Failed to add attachments to prompt history: {e}")

def create_prompt_history_record(
    content_id: int,
    prompt_data: Optional[str],
    prompt_session_id: Optional[str] = None,
    user_id: Optional[int] = None,
    context_override: Optional[bool] = False,
    image_base_64: Optional[List[str]] = None,
    image_attachment_mode: Optional[str] = None,
    category_id: Optional[int] = None,
    context: Optional[str] = None
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


    print(f"Creating new prompt history record for session ID {prompt_session_id}")
    print(f"Prompt Data: {prompt_data}")
    print(f"Context Override: {context}")
    
    prompt_history = db.create("prompt_history", prompt_history_dict)

    if not prompt_history:
        raise Exception("Failed to create prompt history")
    
    if image_base_64 and len(image_base_64) > 0:
        for img in image_base_64: 
            print(f"Adding attachment to prompt history ID {prompt_history['id']}")
            add_attachments_to_prompt_history(db, prompt_history["id"], img)
            
    # Dedup: projects already generated for this page must not reappear as new
    seen_items = _get_seen_project_names(db, content_id)

    # Retrieve context for the draft prompt (not used here but could be logged or processed)
    rag = RagModule()
    rag_result = rag.rag_entry_point(
        query=prompt_data,
        user_id=user_id,
        context_override=context_override,
        image_base_64=image_base_64,
        prompt_session_id=prompt_session_id,
        image_attachment_mode=image_attachment_mode,
        category_id=category_id,
        context=context,
        seen_items=seen_items
    )
    
    # Extract text response from the result dictionary
    ai_response = rag_result.get("text", "") if isinstance(rag_result, dict) else str(rag_result)

    images_generated = rag_result.get("images", []) if isinstance(rag_result, dict) else []
    images = []

    if images_generated and len(images_generated) > 0:
        for img in images_generated:
            print(f"Uploading generated image for prompt history ID {prompt_history['id']}")
            img_s3_url = upload_base64_image_to_s3(img, prefix="generated/generated_images")
            images.append(img_s3_url)

    update_data = {
        "user_prompt": prompt_data,
        "prompt_action": "DRAFT",
        "ai_response": json.dumps({
            "text": ai_response,
            "images": images if len(images) > 0 else None,
            "sources": rag_result.get("sources") or None if isinstance(rag_result, dict) else None,
            "excluded_seen": rag_result.get("excluded_seen") or 0 if isinstance(rag_result, dict) else 0
        })
    }


    updated_records = db.update(
        "prompt_history",
        data=update_data,
        conditions={"id": prompt_history["id"]}
    )

    if not updated_records or len(updated_records) == 0:
        raise Exception("Failed to update prompt history")
    
    return prompt_session_id


def add_draft_to_prompt_history(
    prompt_text: str,
    prompt_session_id: Optional[str] = None,
    content_id: Optional[int] = None,
    user_id: Optional[int] = None,
    context_override: Optional[bool] = False,
    image_base_64: Optional[List[str]] = None,
    category_id: Optional[int] = None,
    image_attachment_mode: Optional[str] = None,
    context: Optional[str] = None
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
    
    # Generate prompt_session_id if not provided
    if not prompt_session_id:
        prompt_session_id = str(uuid.uuid4())
    
    # content_id can be None - no need to set a default
    
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

    context = context

    # Rejected drafts for this content become an avoid signal for the new draft
    rejected_feedback = _get_rejected_feedback(db, content_id)

    # The page's configured climate pillar beats keyword guessing
    sub_category = _get_page_sub_category(db, content_id)

    # Multi-turn: prior exchanges of this session let follow-ups build on them
    conversation_history = _get_conversation_history(db, prompt_session_id)

    # Dedup: projects already generated for this page must not reappear as new
    seen_items = _get_seen_project_names(db, content_id)

    rag = RagModule()
    rag_result = rag.rag_entry_point(
        query=prompt_text,
        user_id=user_id,
        context_override=context_override,
        image_base_64=image_base_64,
        image_attachment_mode=image_attachment_mode,
        category_id=category_id,
        context=context,
        rejected_feedback=rejected_feedback,
        sub_category=sub_category,
        conversation_history=conversation_history,
        seen_items=seen_items
    )

    # Extract text response from the result dictionary
    ai_response = rag_result.get("text", "") if isinstance(rag_result, dict) else str(rag_result)
    images_generated = rag_result.get("images", []) if isinstance(rag_result, dict) else []
    images = []

    if images_generated and len(images_generated) > 0:
        for img in images_generated:
            print(f"Uploading generated image for prompt history session ID {prompt_session_id}")
            img_s3_url = upload_base64_image_to_s3(img, prefix="generated/generated_images")
            images.append(img_s3_url)

    if existing_records and len(existing_records) > 0:

        # Update the existing record
        existing_record = existing_records[0]

        if image_base_64 and len(image_base_64) > 0:
            for img in image_base_64: 
                print(f"Adding attachment to prompt history ID {existing_record['id']}")
                add_attachments_to_prompt_history(db, existing_record["id"], img)
        else:
            print("No attachments to add to prompt history")
        
        update_data = {
            "user_prompt": prompt_text,
            "prompt_action": "DRAFT",
            "ai_response": json.dumps({
                "text": ai_response,
                "images": images if len(images) > 0 else None,
                "sources": rag_result.get("sources") or None if isinstance(rag_result, dict) else None,
                "excluded_seen": rag_result.get("excluded_seen") or 0 if isinstance(rag_result, dict) else 0
            })
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
            "ai_response": json.dumps({
                "text": ai_response,
                "images": images if len(images) > 0 else None,
                "sources": rag_result.get("sources") or None if isinstance(rag_result, dict) else None,
                "excluded_seen": rag_result.get("excluded_seen") or 0 if isinstance(rag_result, dict) else 0
            }),
            "prompt_type": "TEXT",
            "prompt_action": "DRAFT"  # Default to DRAFT for drafts
        }
        
        prompt_history = db.create("prompt_history", prompt_history_dict)
        
        if not prompt_history:
            raise Exception("Failed to create prompt history")
        
        if image_base_64 and len(image_base_64) > 0:
            for img in image_base_64: 
                print(f"Adding attachment to prompt history ID {prompt_history['id']}")
                add_attachments_to_prompt_history(db, prompt_history["id"], img)
        else:
            print("No attachments to add to prompt history")
        
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
        order_by=[("created_on", True)]  
    )
    
    if not prompt_histories:
        return []
    
    # Convert to response models
    response_list = []

    for ph in prompt_histories:
        attachments = db.read(
            "prompt_attachments",
            conditions={
                "prompt_history_id": ph["id"]
            }
        )

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
            updated_on=ph["updated_on"],
            attachments=attachments if attachments else [] 
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

    record = dict(updated_records[0]._mapping)

    # Training signal must never break the approve/reject action itself
    try:
        _sync_approval_training_data(record)
    except Exception as e:
        logger.warning(f"Training-signal sync failed (action saved regardless): {e}")

    return record


def get_content_version_history(content_id: int) -> List[Dict[str, Any]]:
    """
    Every saved version of a piece of content, newest first, across all
    sessions. Versions with no usable response text (errors, empty) are
    skipped. Feeds the Draft History panel.
    """
    if not content_id:
        return []
    db = PostgresDB()
    rows = db.read(
        "prompt_history",
        conditions={"content_id": content_id, "deleted_on": None},
        order_by=[("created_on", False)],
    )
    versions = []
    for row in rows or []:
        text = _extract_response_text(row.get("ai_response"))
        if not text:
            continue
        action = row.get("prompt_action")
        action = getattr(action, "value", action)  # unwrap enum if present
        created = row.get("created_on")
        versions.append({
            "id": row.get("id"),
            "created_on": created.isoformat() if hasattr(created, "isoformat") else created,
            "user_prompt": row.get("user_prompt") or "",
            "prompt_action": action,
            "text": text,
            "preview": text[:120],
        })
    return versions


def restore_content_version(
    content_id: int, version_id: int, user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Non-destructive restore: copy the chosen version's response into a NEW
    latest prompt_history row (prompt_action=RESTORE). The original versions
    are left untouched, so nothing is ever lost.
    """
    db = PostgresDB()

    rows = db.read(
        "prompt_history",
        conditions={"id": version_id, "content_id": content_id, "deleted_on": None},
        limit=1,
    )
    if not rows:
        raise ValueError(f"Version {version_id} not found for content {content_id}")
    source = rows[0]

    # Reuse the content's current session so the restored copy lands in the
    # same thread; fall back to the source version's own session.
    latest = db.read(
        "prompt_history",
        conditions={"content_id": content_id, "deleted_on": None},
        columns=["prompt_session_id"],
        order_by=[("created_on", False)],
        limit=1,
    )
    session_id = (latest[0].get("prompt_session_id") if latest
                  else source.get("prompt_session_id")) or str(uuid.uuid4())

    src_created = source.get("created_on")
    src_ts = src_created.strftime("%b %d, %Y %I:%M %p") if hasattr(src_created, "strftime") else str(src_created)

    new_row = db.create("prompt_history", {
        "prompt_session_id": session_id,
        "content_id": content_id,
        "user_prompt": f"Restored version from {src_ts}",
        "ai_response": source.get("ai_response"),
        "prompt_type": "TEXT",
        "prompt_action": "RESTORE",
    })
    if not new_row:
        raise Exception("Failed to create restored version")
    logger.info(f"Restored version {version_id} as new row {new_row['id']} for content {content_id}")
    return dict(new_row)


def get_all_prompts(
    prompt_session_id: Optional[str] = None,
    content_id: Optional[int] = None
):
    """
    Retrieve all prompt history records for a given session and content.
    
    Args:
        prompt_session_id: UUID of the prompt session
        content_id: ID of the content record           
    """

    db = PostgresDB()

    data = {}
    params = []


    query = """
        select prompt_session_id, id, content_id, user_prompt, ai_response, created_on, deleted_on
        from prompt_history
    """

    if prompt_session_id or content_id:
        query += " where "
        conditions = []

        if prompt_session_id:
            conditions.append("prompt_session_id = %s")
            params.append(prompt_session_id)
        if content_id:
            conditions.append("content_id = %s")
            params.append(content_id)

        query += " AND ".join(conditions)
        query += " AND deleted_on IS NULL"
    query += " ORDER BY id DESC"
    prompt_histories = db.execute_raw_sql(query, tuple(params))

    for ph in prompt_histories:

        session_id = (''.join(ph[0].split("-")[:4])).replace(" - ", "")

        if session_id not in data:
            data[session_id] = {}
        
        data[session_id].update({
            "id": ph[1],
            "content_id": ph[2],
            "user_prompt": ph[3],
            "created_on": ph[5],
            "deleted_on": ph[6]
        })

        if ph[4]:
            try:
                data[session_id]["ai_response"] = json.loads(ph[4]) if ph[4] else None
            except Exception as e:
                data[session_id]["ai_response"] = ph[4]

    return data