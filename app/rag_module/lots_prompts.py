from rag_module.prompt_rules import LottiePrompts
from rag_module.static_links import get_links_as_string

def build_lots_prompt(
        query: str = None,
        context_str: str = None,
        topic: str = None,
        max_lines: int = None,
        line_rule: str = ""
) -> str:
    """
    Generates an optimized context-bound prompt for the LOTS category.
    
    Optimized to:
    1. Extract the specific Entity Title, Year, and Subject details from context.
    2. Enforce the exact Phycolabs card format (Title / Year / Tagline / Subject).
    3. Include the mandatory Lottie institutional footer and explanation block.
    """

    if not context_str:
        context_str = "No additional context provided."

    # fallback label if extraction fails
    topic_label = topic if topic else "the initiative or innovation described in the context"

    if not query:
        query = "Provide a detailed LOTS-style analysis of the given topic."

    # --- MODE 1: CONCISE SUMMARY (Short form) ---
    if max_lines is not None:
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

CONTENT SOURCE RULE (MANDATORY):
The CONTEXT section below is your sole source of facts.
Extract all names, years, organizations, and details directly from it.
Do NOT fabricate or invent any information not present in the context.

TASK:
Produce a concise summary of the LOTS entry constrained to the line limits provided.

STRICT OUTPUT RULES:
{line_rule}
- Each line must be one complete sentence.
- Do NOT add information not present in the context.
- Do NOT use headings, labels, or section titles.
- Output ONLY the final answer.

USER QUESTION:
{query}

CONTEXT:
{context_str}
"""

    # --- MODE 2: FULL EDITORIAL CARD (The Phycolabs Style) ---
    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

CONTENT SOURCE RULE (MANDATORY):
The KNOWLEDGE CONTEXT section below is your sole source of facts.
Use it as the source material to generate the LOTS card.
Extract all names, years, organizations, technologies, and details directly from it.
Do NOT fabricate or invent any information not present in the context.

You are an expert content author for Lottie, specializing in the "LOTS" category which features new initiatives and biotechnological innovations.

TASK:
1. IDENTIFY TOPIC: From the KNOWLEDGE CONTEXT, identify the primary initiative, person, or organization.
2. DYNAMIC EXTRACTION: Extract the Year, a Tagline (short uppercase punchy line), and a Subject Title (sentence-style heading in all caps).
3. STRUCTURE: Produce the LOTS card output exactly as specified below.

USER QUESTION:
{query}

==================================================
REQUIRED LOTS STRUCTURE (FOLLOW EXACTLY)
==================================================

[INITIATIVE/FIRM NAME]
/
[YEAR]

[UPPERCASE TAGLINE - e.g. FASHION MEETS BIOTECH]
[UPPERCASE SUBJECT TITLE - e.g. HOW BIOTECHNOLOGY CAN TRANSFORM THE INDUSTRY]

Source: © [Name of Organization or Person]
www:[Website URL]

[DESCRIPTION PARAGRAPHS]
- Write 2-3 short, technical but evocative paragraphs.
- Focus on the mission, the specific technology or process, and the regenerative/sustainable impact.
- Use natural flowing text; do not use bullet points or dashes.

More

==================================================
FOOTER (MANDATORY AT THE VERY END)
==================================================

Attributions
Foundation for Climate Restoration
Solution Series content and sources

Go Deeper
Learn more about the identified topic from Foundation for Climate Restoration
- white paper
- animated video
- expert panel discussion

Subscribe
Subscribe to the Lot21 QUARTERLY newsletter for quick updates and links to learn more.

==================================================
KNOWLEDGE CONTEXT:
==================================================
{context_str}


ADDITIONAL RESEARCH SOURCES (FALLBACK):
{get_links_as_string(["lots", "policy"])}

"""
# After the footer, add exactly:
# ---BEGIN EXPLANATION---
# Briefly explain how you identified the initiative, year, and subject details from the context and confirmed the card formatting.
# ---END EXPLANATION---