import re

RANGE_REGEX = re.compile(r'(\d+)\s*(?:to|-)\s*(\d+)\s*(?:line|lines)', re.I)

def detect_max_lines_from_query(query: str):
    """
    Returns:
      - int → exact line count
      - tuple(min, max) → range
      - None → not specified
    """
    if not query:
        return None

    q = query.lower()

    # NEW: "2 to 3 lines", "2-3 lines"
    range_match = RANGE_REGEX.search(q)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        low, high = max(1, low), min(high, 10)
        if low <= high:
            return (low, high)

    # Existing exact patterns
    match = re.search(r'(\d+)\s*[- ]*(line|lines)', q)
    if match:
        lines = int(match.group(1))
        return max(1, min(lines, 10))

    # Semantic shortcuts (unchanged)
    if any(p in q for p in ["one line", "single line", "one-line"]):
        return 1

    if any(p in q for p in [
        "short summary", "brief summary", "very short",
        "quick summary", "tl;dr"
    ]):
        return 3

    if any(p in q for p in ["summary", "summarize"]):
        return 5

    return None


def line_rule(max_lines):
    if isinstance(max_lines, tuple):
        return f"- Write BETWEEN {max_lines[0]} AND {max_lines[1]} lines."
    return f"- Write EXACTLY {max_lines} lines."