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

    return ""
