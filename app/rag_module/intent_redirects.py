import re

REWRITE_KEYWORDS = [
    # --- Core Actions ---
    "refine", "rewrite", "rephrase", "edit", "revise", "reword", "reframe", "restyle",
    "modify", "alter", "change", "update", "polish", "iterate", "transform", "convert",
    "fix", "correct", "adjust", "redo", "clean up", "amend", "overhaul",
    "change the", "alter the", "modify the", "update the", "rewrite for clarity",
    "generate a clearer version of", "make it more", "make it less", 
    "make it more like", "make it more suitable for","Generate the"

    # --- Conciseness & Compression ---
    "condense", "shorten", "simplify", "concise", "tighten", "streamline", "compress",
    "trim", "cut down", "boil down", "summarize", "recap", "abbreviate", "compact",
    "make it concise", "brief", "briefly explain", "briefly summarize", "briefly rewrite",
    "summarize and rewrite", "make it more concise",

    # --- Expansion & Detail ---
    "elaborate", "expand", "flesh out", "add detail", "go deeper", "explain more",
    "provide more info on", "detail the", "broaden", "amplify",

    # --- Quality & Readability ---
    "improve", "enhance", "optimize", "smooth", "readability", "clarity", "flow",
    "clearer", "readable", "professional", "formal", "informal", "simpler",
    "engaging", "compelling", "persuasive", "punchy", "technical", "academic",
    "improve readability", "improve flow", "improve clarity", "make it clearer",
    "make it readable",

    # --- Specific Lottie Contextual Rewrites ---
    "tone down", "make it restorative", "align with mission", "center on welfare",
    "make it solution-oriented", "professionalize", "soften", "bolden",

    # --- Formality & Tone Adjustments ---
    "make it formal", "make it informal", "make it professional", "make it simpler",
    "make it more engaging", "make it more compelling", "make it more persuasive",

    # --- Instructional Phrases ---
    "explain", "what is", "give me a summary", "explain in simple terms",
    "explain like i'm five", "eli5", "clarify", "explain me", "give me a summary of",
    "simplify the explanation of"
]

def is_rewrite_intent(query: str) -> bool:
    """
    Determines if the user wants to refine existing context or generate new content.
    Optimized for high-speed pattern matching and natural language boundary detection.
    """
    if not query:
        return False

    q = query.lower().strip()

    # 1. Primary Start-Word Check (Optimization)
    # Using a set for O(1) lookup on the most common command verbs
    primary_verbs = {
        "rewrite", "rephrase", "refine", "edit", "revise", "reword", "polish", 
        "simplify", "condense", "shorten", "streamline", "improve", "enhance", 
        "update", "change", "alter", "modify", "elaborate", "explain", "Generate"
    }
    
    words = q.split()
    if words and words[0] in primary_verbs:
        return True

    # 2. Comprehensive Phrase Check with Regex Word Boundaries
    # This replaces the need for f" {p} " and startswith() as regex \b 
    # handles start, end, and punctuation (like commas or periods) automatically.
    if any(re.search(r'\b' + re.escape(p) + r'\b', q) for p in REWRITE_KEYWORDS):
        return True

    # 3. Structural Pattern Fallback
    # Catches conversational intents that don't always use the keywords as standalone words
    return q.startswith("make it") or "rewrite for" in q or "rewrite to" in q