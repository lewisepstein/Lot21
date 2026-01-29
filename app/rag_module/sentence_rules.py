import re

SENTENCE_RANGE_REGEX = re.compile(
    r'(\d+)\s*(?:to|-)\s*(\d+)\s*sentences?',
    re.I
)
SENTENCE_EXACT_REGEX = re.compile(
    r'(\d+)\s*sentences?',
    re.I
)

def detect_sentence_limit(query: str):
    if not query:
        return None

    q = query.lower()

    range_match = SENTENCE_RANGE_REGEX.search(q)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return (low, high)

    exact_match = SENTENCE_EXACT_REGEX.search(q)
    if exact_match:
        return int(exact_match.group(1))

    return None

