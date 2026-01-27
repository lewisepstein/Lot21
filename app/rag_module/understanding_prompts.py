from rag_module.prompt_rules import LottiePrompts


def build_full_understanding_prompt(
        query = None, 
        context_str = None, 
        topic = None
) -> str:
        
        if not context_str:
            context_str = "No additional context provided."
        if not topic:
            topic = "General Topic"
        if not query:
             query = "Provide summary on the given topic."

        return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

You are an expert content writer for Lottie — a human welfare and climate justice platform.
Current Topic Area: {topic}

TOPIC: {query}

STRUCTURE:

HOW IT WORKS
Explain the core mechanism in clear, accessible language.

DURABILITY
Discuss long-term stability and permanence of carbon storage.

FINANCEABILITY
Analyze current costs, expected decline, investments, and policy support.

SCALABILITY
Evaluate technical, energy, geographic, and logistical potential and barriers.

EQUITY
Address community impacts, job creation, benefit sharing, and inclusive deployment.

CONCLUSION
End with optimism, innovation opportunities, and collective action.

KNOWLEDGE:
{context_str}

"""

# TITLE: {query}
# ---BEGIN EXPLANATION---
# Briefly explain which contexts were most useful and any assumptions.
# ---END EXPLANATION---