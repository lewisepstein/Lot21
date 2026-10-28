"""
Standing instructions: rules a user saves once (Settings > Content Style)
that Lottie applies to every text prompt in Lot21 AI and Free Form AI.
"""
from typing import Optional

from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger

logger = get_logger(__name__)

MAX_STANDING_INSTRUCTIONS_CHARS = 4000


def get_standing_instructions(user_id: Optional[int]) -> str:
    """
    The user's saved instructions, or "" when none are saved. Never raises:
    a read problem (e.g. the column not migrated yet) must not block generation.
    """
    if not user_id:
        return ""
    try:
        rows = PostgresDB().read(
            "users", conditions={"id": user_id}, columns=["standing_instructions"]
        )
        return ((rows[0].get("standing_instructions") if rows else None) or "").strip()
    except Exception as e:
        logger.warning(f"Could not read standing instructions for user {user_id}: {e}")
        return ""


def save_standing_instructions(user_id: int, instructions: str) -> str:
    """Save (or clear, when empty) the user's instructions; returns what was stored."""
    instructions = (instructions or "").strip()
    if len(instructions) > MAX_STANDING_INSTRUCTIONS_CHARS:
        raise ValueError(
            f"Standing instructions are limited to {MAX_STANDING_INSTRUCTIONS_CHARS} characters."
        )
    PostgresDB().update(
        "users", {"standing_instructions": instructions or None}, {"id": user_id}
    )
    return instructions


def standing_instructions_block(user_id: Optional[int]) -> str:
    """Prompt section carrying the user's saved instructions; "" when there are none."""
    instructions = get_standing_instructions(user_id)
    if not instructions:
        return ""
    return (
        "\n\nSTANDING INSTRUCTIONS (saved by the user; follow them in every response. "
        "If the current request explicitly asks for something different, the request wins):\n"
        f"{instructions}"
    )
