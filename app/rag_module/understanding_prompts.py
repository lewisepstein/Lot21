from rag_module.prompt_rules import LottiePrompts

def build_full_understanding_prompt(
        query=None,
        context_str=None,
        topic=None,
        max_lines=None,
        line_rule=None
) -> str:

    if not context_str:
        context_str = "No additional context provided."
    if not topic:
        topic = "General Topic"
    if not query:
        query = "Provide summary on the given topic."

    # -------- CONTEXT-BOUND SUMMARY MODE --------
    if max_lines is not None:
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

CRITICAL CONTEXT RULE (MANDATORY):

You must answer using ONLY the information present in the CONTEXT section below.

If the user question is NOT related to the CONTEXT, or cannot be answered
directly from it, you MUST NOT generate an answer.

Instead, respond with EXACTLY this sentence and nothing else:

"This question is outside the scope of the provided context."

TASK:
Provide a concise summary based strictly on the context.

STRICT OUTPUT RULES:
{line_rule}
- Each line must be one complete sentence.
- Do NOT add information not present in the context.
- Do NOT use headings, labels, or section titles.
- Do NOT explain your reasoning or rule checks.
- Output ONLY the final answer.

USER QUESTION:
{query}

CONTEXT:
{context_str}
"""

    # -------- CONTEXT-BOUND FULL MODE --------
    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

CRITICAL CONTEXT RULE (MANDATORY):

You must answer using ONLY the information present in the CONTEXT section below.

If the user question is NOT related to the CONTEXT, or cannot be answered
directly from it, you MUST NOT generate an answer.

Instead, respond with EXACTLY this sentence and nothing else:

"This question is outside the scope of the provided context."

You are an expert content writer for Lottie.
Current Topic Area: {topic}

USER QUESTION:
{query}

STRUCTURE:

HOW IT WORKS
Explain using ONLY the provided context.

DURABILITY
Discuss ONLY what is supported by the context.

FINANCEABILITY
If not mentioned in context, do not infer.

SCALABILITY
Base analysis strictly on context.

EQUITY
Address ONLY if present in context.

CONCLUSION
Summarize without adding new facts.

CONTEXT:
{context_str}
"""
