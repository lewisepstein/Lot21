from rag_module.prompt_rules import LottiePrompts


def build_definition_prompt(query, context_str, sentence_limit):
    if isinstance(sentence_limit, tuple):
        rule = f"- Write BETWEEN {sentence_limit[0]} AND {sentence_limit[1]} sentences."
    else:
        rule = f"- Write EXACTLY {sentence_limit} sentences."

    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

TASK:
Define the concept using ONLY the provided context.

STRICT OUTPUT RULES:
{rule}
- Do NOT use section titles.
- Do NOT explain your reasoning.
- Output ONLY the final answer.

CONTEXT:
{context_str}
"""
