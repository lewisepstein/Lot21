import re

RANGE_REGEX = re.compile(r'(\d+)\s*(?:to|-)\s*(\d+)\s*(?:line|lines)', re.I)
SENTENCE_RANGE_REGEX = re.compile(r'(\d+)\s*(?:to|-)\s*(\d+)\s*(?:sentence|sentences)', re.I)
SENTENCE_EXACT_REGEX = re.compile(r'(\d+)\s*(?:sentence|sentences)', re.I)

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

def detect_sentence_limit(query: str):
    """
    Returns:
      - int → exact sentence count
      - tuple(min, max) → range
      - None → not specified
    """
    if not query:
        return None
    
    q = query.lower()
    
    # Range: "2 to 3 sentences", "2-3 sentences"
    range_match = SENTENCE_RANGE_REGEX.search(q)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        low, high = max(1, low), min(high, 20)
        if low <= high:
            return (low, high)

    # Exact: "2 sentences"
    match = SENTENCE_EXACT_REGEX.search(q)
    if match:
        count = int(match.group(1))
        return max(1, min(count, 20))
        
    return None

def line_rule(max_lines):
    """
    Legacy function name kept for compatibility, but now returns stricter constraints.
    Can handle both line counts (int/tuple) and is used when line limit is detected.
    """
    if isinstance(max_lines, tuple):
        return f"- Write BETWEEN {max_lines[0]} AND {max_lines[1]} lines. Do NOT exceed this limit."
    return f"- Write EXACTLY {max_lines} lines. Do NOT write more."

def build_length_constraint(max_lines=None, max_sentences=None):
    """
    Builds the final constraint string based on detected limits.
    Prioritizes sentence limits if both are present (usually more specific).
    """
    if max_sentences:
        if isinstance(max_sentences, tuple):
            return f"- Write BETWEEN {max_sentences[0]} AND {max_sentences[1]} sentences. Do NOT exceed this limit. Keep it concise."
        return f"- Write EXACTLY {max_sentences} sentences. Do NOT write more. Keep it concise."

    if max_lines:
        return line_rule(max_lines)

    return ""