import re

PARA_COUNT_REGEX = re.compile(r'(\d+)\s+paragraph', re.I)

def extract_paragraph_count(query: str):
    """
    Returns:
      - int (exact paragraph count)
      - tuple(min, max) for vague counts
      - None if not specified
    """
    if not query:
        return None

    q = query.lower()

    # Exact number: "2 paragraphs"
    match = PARA_COUNT_REGEX.search(q)
    if match:
        return int(match.group(1))

    # Vague language
    if "single paragraph" in q or "one paragraph" in q:
        return 1

    if "few paragraphs" in q:
        return (2, 3)

    if "multiple paragraphs" in q:
        return (2, 4)

    if "short paragraphs" in q:
        return (2, 3)

    return None



# Updated regex to include standard digits (1, 2, 3...) alongside ordinals
ORDINAL_REGEX = re.compile(
    r'\b(\d+(?:st|nd|rd|th)?|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last)\b', 
    re.I
)

def detect_target_paragraph(query: str):
    """
    Returns specific paragraph target string (e.g., "1st", "last", "3rd")
    or None if no specific target is found.
    """
    if not query:
        return None
    
    q = query.lower()
    
    # Check for "paragraph X" or "X paragraph" where X is ordinal
    # We look for the ordinal word in proximity to "paragraph"
    if "paragraph" in q:
        match = ORDINAL_REGEX.search(q)
        if match:
             return match.group(1)
             
    return None


def build_paragraph_constraint(paragraphs):
    if isinstance(paragraphs, int):
        return f"""
OUTPUT CONSTRAINT:
- Rewrite the content into EXACTLY {paragraphs} paragraphs.
- Separate paragraphs with a single line break.
- Do NOT add or remove information.
"""

    if isinstance(paragraphs, tuple):
        min_p, max_p = paragraphs
        return f"""
OUTPUT CONSTRAINT:
- Rewrite the content into BETWEEN {min_p} AND {max_p} paragraphs.
- Separate paragraphs with a single line break.
- Do NOT add or remove information.
"""

    if isinstance(paragraphs, str):
        return f"""
OUTPUT CONSTRAINT:
- Rewrite ONLY the {paragraphs} paragraph.
- Do NOT rewrite other paragraphs.
- Maintain the flow with surrounding content if applicable.
"""

    return ""
