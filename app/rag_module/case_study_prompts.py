from rag_module.prompt_rules import LottiePrompts
from rag_module.static_links import get_links_as_string

def build_project_case_study_prompt(
        query: str = None, 
        context_str: str = None, 
        project_sources: dict = None,
        category_id: int = 1,
        line_rule: str = ""
) -> str:
    """
    Generates a prompt to produce a Project Case Study in the exact 
    Lottie visual/editorial style.
    
    Categories:
    1: Adapt (climate resilience)
    2: Mitigate (carbon reduction)
    3: Restore (nature restoration)
    """
    
    # 1. Map Category Meta-data
    CATEGORY_META = {
        1: {"name": "Adapt", "tagline": "climate resilience", "focus": "climate adaptation"},
        2: {"name": "Mitigate", "tagline": "carbon reduction", "focus": "carbon mitigation"},
        3: {"name": "Restore", "tagline": "nature restoration", "focus": "ecological restoration"}
    }
    
    meta = CATEGORY_META.get(category_id, CATEGORY_META[1])
    links_str = "\n".join([f"- {name}: {url}" for name, url in project_sources.items()]) if project_sources else "No external sources provided."

    # 2. Build the Prompt
    return f"""{LottiePrompts.GUARDRAIL_RULES}

                {LottiePrompts.PLAIN_TEXT_RULES}

                {line_rule}

                You are an expert project analyst for Lottie.
                Your task is to generate or refine a Project Case Study using the Lottie minimalist card format.

                TOPIC: {query}

                ==================================================
                REQUIRED PROJECT STRUCTURE (FOLLOW EXACTLY)
                ==================================================

                {meta['name']} — {meta['tagline']}
                Collected works at the forefront of {meta['focus']}

                [PROJECT TITLE]
                
                [YEARS] - [STATUS/AWARDS]
                Source: © [FIRM NAME]
                www:[WEBSITE DOMAIN]

                [DESCRIPTION PARAGRAPHS]
                - Write 2 natural flowing paragraphs. 
                - Do NOT use bullet points.
                - Focus on site transformation, specific climate features (e.g., flood protection, water capture), and the synergy between nature and infrastructure.
                - Use technical yet evocative language.

                ==================================================
                KNOWLEDGE CONTEXT:
                ==================================================
                {context_str}

                EXTERNAL SOURCES FOR REFERENCE:
                {links_str}

                
ADDITIONAL RESEARCH SOURCES (FALLBACK):
{get_links_as_string(["projects", "policy"])}

"""


# After the project content, add exactly:
#                 ---BEGIN EXPLANATION---
#                 Briefly explain which technical details were pulled from the context and any assumptions made about the project status or firm.
#                 ---END EXPLANATION---
