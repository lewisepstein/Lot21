
from rag_module.prompt_rules import LottiePrompts


def build_project_case_study_prompt(query, context_str, project_sources):
        links_str = "\n".join([f"- {name}: {url}" for name, url in project_sources.items()])
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

You are an expert project analyst for Lottie.

TOPIC: {query}

KNOWLEDGE:
{context_str}

EXTERNAL SOURCES:
{links_str}

---BEGIN EXPLANATION---
Briefly explain sources used and any technical assumptions.
---END EXPLANATION---
"""

    