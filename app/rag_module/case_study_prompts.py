
from rag_module.prompt_rules import LottiePrompts


def build_project_case_study_prompt(
        query=None, 
        context_str=None, 
        project_sources=None
)-> str:
        links_str = "\n".join([f"- {name}: {url}" for name, url in project_sources.items()])
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

You are an expert project analyst for Lottie.

TOPIC: {query}

KNOWLEDGE:
{context_str}

EXTERNAL SOURCES:
{links_str}

"""

    