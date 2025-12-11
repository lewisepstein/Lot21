"""
Helper utility functions for common operations.
"""
from typing import Optional
from datetime import datetime
import logging

from service_utils.date_exceptions import DateConversionError, InvalidDateFormatError

# Set up logging
logger = logging.getLogger(__name__)


def convert_datetime_to_formatted_string(
    dt: Optional[datetime],
    format_type: str = "display"
) -> Optional[str]:
    """
    Convert datetime object to formatted string.
    
    Args:
        dt: Datetime object to convert
        format_type: Type of format - "display" for readable format,
                    "iso" for ISO format
    
    Returns:
        Formatted datetime string or None if input is None
        
    Raises:
        DateConversionError: If conversion fails
        InvalidDateFormatError: If format_type is invalid
    """
    if dt is None:
        return None
    
    try:
        if not isinstance(dt, datetime):
            raise DateConversionError(
                f"Expected datetime object, got {type(dt).__name__}"
            )
        
        if format_type == "display":
            # Format: 'DDth Mon, YYYY HH:MM AM/PM'
            # Get day with ordinal suffix
            day = dt.day
            if 10 <= day % 100 <= 20:
                suffix = 'th'
            else:
                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
            
            # Format: 11th Dec, 2025 03:15 PM
            return dt.strftime(f"%d<sup>{suffix}</sup> %b, %Y %I:%M %p")
        elif format_type == "iso":
            # ISO 8601 format
            return dt.isoformat()
        else:
            raise InvalidDateFormatError(
                f"Invalid format_type: {format_type}. "
                "Use 'display' or 'iso'"
            )
            
    except (AttributeError, ValueError) as e:
        logger.error(f"Error converting datetime: {e}")
        raise DateConversionError(
            f"Failed to convert datetime to {format_type} format: {str(e)}"
        ) from e
