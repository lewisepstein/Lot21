from rag_module.prompt_rules import LottiePrompts


def build_policy_prompt(query, context_str, scope, sources):
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

You are an expert policy analyst for Lottie.

TOPIC: {query}

SCOPE: {scope}

SOURCES:
{sources}

INTERNAL RESEARCH:
{context_str}

---BEGIN EXPLANATION---
Briefly explain how the policy data was sourced and how it supports decarbonization.
---END EXPLANATION---
"""

    