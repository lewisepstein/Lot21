
REWRITE_KEYWORDS = [
    # Core rewrite actions
    "refine",
    "rewrite",
    "rephrase",
    "edit",
    "revise",
    "explain"

    # Conciseness & clarity
    "condense",
    "shorten",
    "simplify",
    "make it concise",
    "tighten",
    "streamline",
    "clarify",
    "clean up",

    # Quality improvement
    "improve",
    "polish",
    "enhance",
    "smooth",
    "optimize",

    # Tone & readability
    "make it clearer",
    "make it readable",
    "improve readability",
    "improve flow",
    "improve clarity",

    # Style adjustments
    "reword",
    "reframe",
    "restyle",
    "rewrite for clarity",

    # Compression / restructuring
    "summarize and rewrite",
    "compress",
    "trim",
    "cut down",

    # Formality changes (still rewrite)
    "make it formal",
    "make it informal",
    "make it professional",
    "make it simpler",
]

def is_rewrite_intent(query: str) -> bool:
    if not query:
        return False

    q = query.lower().strip()

    # Must indicate an action on existing text
    rewrite_phrases = [
        "rewrite",
        "rephrase",
        "refine",
        "edit",
        "revise",
        "reword",
        "polish",
        "simplify",
        "condense",
        "shorten",
        "streamline",
        "clean up",
        "make it",
        "improve",
        "enhance",
        "clarity",
        "readability",
        "explain",
    ]

    return any(q.startswith(p) or f" {p} " in q for p in rewrite_phrases)