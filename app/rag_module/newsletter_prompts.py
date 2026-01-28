
from rag_module.prompt_rules import LottiePrompts


def build_quarterly_newsletter_prompt(query, context_str, season, year):
        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

{season.upper()} {year}
/ quarterly banner

KNOWLEDGE CONTEXT:
{context_str}

"""