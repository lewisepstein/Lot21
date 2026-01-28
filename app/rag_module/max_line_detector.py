import re

def detect_max_lines_from_query(query: str) -> int | None:
    """
    Detects requested summary length from user text.
    Returns number of lines or None if not specified.
    """

    if not query:
        return None

    q = query.lower()

    # Explicit numeric patterns: "4 lines", "in 3 lines", "2-line summary"
    match = re.search(r'(\d+)\s*[- ]*(line|lines)', q)
    if match:
        lines = int(match.group(1))
        return max(1, min(lines, 10))  # clamp safety (1–10)

    # Common semantic shortcuts
    if any(phrase in q for phrase in [
        "one line", "single line", "one-line"
    ]):
        return 1

    if any(phrase in q for phrase in [
        "short summary", "brief summary", "very short",
        "quick summary", "tl;dr"
    ]):
        return 3

    if any(phrase in q for phrase in [
        "summary", "summarize"
    ]):
        return 5

    return None