
from rag_module.prompt_rules import ALPHA_REGEX, LottiePrompts


def build_resource_prompt(query, context_str, resource_type, sources):
        alphabet_instruction = ""
        alpha_match = ALPHA_REGEX.search(query)
        if alpha_match:
            letter = alpha_match.group(1) if alpha_match.group(1) else "A"
            alphabet_instruction = f"Provide materials specifically starting with the letter '{letter.upper()}' or in alphabetical sequence."

        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

You are an expert material analyst for Lottie.

TOPIC: {query}
{alphabet_instruction}

KNOWLEDGE CONTEXT:
{context_str}

AUTHORITATIVE SOURCES:
{sources}

---BEGIN EXPLANATION---
Briefly explain how the chosen material/tool aligns with decarbonization.
---END EXPLANATION---
"""

    