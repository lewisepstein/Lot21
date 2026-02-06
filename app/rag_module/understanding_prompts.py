from rag_module.prompt_rules import LottiePrompts

def build_full_understanding_prompt(
        query: str = None,
        context_str: str = None,
        topic: str = None,
        max_lines: int = None,
        line_rule: str = ""
) -> str:
    """
    Generates a context-bound prompt for the Understanding category.
    Optimized to:
    1. Extract the specific heading/topic from the context automatically.
    2. Dynamically extract and include "Extra Subheadings" (e.g., 'How it works', 'What is...?') 
       found in the context that aren't part of the standard pillars.
    3. Generate content in a fixed Lottie editorial format with high technical density.
    """

    if not context_str:
        context_str = "No additional context provided."
    
    # We remove the generic fallback string here to prevent the LLM from using it as a title.
    # If no topic is provided, we tell the LLM to identify it purely from context.
    topic_label = topic if topic else "the technical solution described in the context"
    
    if not query:
        query = "Provide technical analysis on the given topic."

    # -------- MODE 1: CONTEXT-BOUND SUMMARY (Concise) --------
    if max_lines is not None:
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

CRITICAL CONTEXT RULE (MANDATORY):
You must answer using ONLY the information present in the CONTEXT section below.
If the query cannot be answered directly from it, respond with EXACTLY:
"This question is outside the scope of the provided context."

TASK:
Provide a concise summary based strictly on the context.

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

    # -------- MODE 2: CONTEXT-BOUND FULL MODE (Editorial Article) --------
    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

CRITICAL CONTEXT RULE (MANDATORY):
You must answer using ONLY the information present in the CONTEXT section below.
If the user question is NOT related to the CONTEXT, respond with EXACTLY:
"This question is outside the scope of the provided context."

You are an expert institutional content writer for Lottie. 

TASK:
1. IDENTIFY TOPIC: From the KNOWLEDGE CONTEXT, identify the primary technical topic (e.g. "Ocean-Based CDR", "Direct Air Capture"). 
   - DO NOT use generic titles like "GENERAL TOPIC" or "ARTICLE".
   - Use the specific technical name found in the text.
2. DYNAMIC EXTRACTION: Scan the context for specific sub-sections that describe the mechanism, definitions, or processes (e.g., "How it works", "What is [Topic]?", "Specific Mechanisms"). 
3. CONTENT DENSITY: Do not summarize aggressively. Include the specific mechanisms and data points found.
4. STRUCTURE: Follow the required structure below. Place any "Extra Subheadings" identified in Step 2 between the Introduction and the Fixed Pillars.

USER QUESTION:
{query}

==================================================
REQUIRED ARTICLE STRUCTURE (FOLLOW EXACTLY)
==================================================

[TITLE]
The specific extracted name of the technical solution in ALL CAPS. 
(Note: Never use "GENERAL TOPIC" or generic placeholders).

[INTRODUCTION & OVERVIEW]
Write 3-5 paragraphs providing a comprehensive overview:
- Start with a "What is [Identified Topic]?" framing if not present as a standalone heading.
- Explain the core motivations (e.g., scalability vs land-based solutions).
- Explicitly mention that the practices vary in durability, financeability, scalability, and equity.

[DYNAMIC EXTRA SUBHEADINGS]
(Extract any specific headings found in the context that provide extra technical detail, such as "How it Works" or "Primary Mechanisms". Generate 2-3 paragraphs for each, including all technical details and terms from the context.)

DURABILITY
Detail storage duration and conditions for permanence based ONLY on context.

SCALABILITY
Explain levels of potential and specific constraints (limited land, ecosystem variables, etc.).

FINANCEABILITY
Provide specific cost ranges and revenue opportunities. Do not omit data.

EQUITY
Discuss social implications, historic inequities, and the need for inclusive governance.

CONCLUSION
- Summarize why the topic is a critical restorative solution.
- Highlight the need for rigorous testing and cross-disciplinary design involvement.
- End with a professional call to action regarding monitoring and verification.

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


"""

# After the footer, add exactly:
# ---BEGIN EXPLANATION---
# Explain how you identified the specific technical title and which "Extra Subheadings" were discovered in the context.
# ---END EXPLANATION---