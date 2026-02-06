from rag_module.prompt_rules import ALPHA_REGEX, LottiePrompts

def build_resource_prompt(query: str, context_str: str, resource_type: str, sources: str) -> str:
    """
    Generates a prompt for the Resources section (Materials or Tools).
    It extracts resource types from the context/query and enforces the 
    exact Lottie editorial format (Heading / Descriptor -> Paragraph -> Listings -> Status).
    """
    
    # 1. Handle alphabetical constraints
    alphabet_instruction = ""
    alpha_match = ALPHA_REGEX.search(query)
    if alpha_match:
        letter = alpha_match.group(1) if alpha_match.group(1) else "A"
        alphabet_instruction = f"ONLY generate entries for resources starting with the letter '{letter.upper()}'."

    # 2. Build the Prompt
    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

You are an expert material and technical resource analyst for Lottie.

TASK:
1. Identify and extract specific resource headings (e.g., "Bamboo", "Beets", "Algae") from the provided KNOWLEDGE CONTEXT or USER QUERY.
2. Generate structured directory entries for each identified heading.
3. If the user specifically asks for a resource in the prompt that is not in the context, use your internal expert knowledge to fulfill the request in the same format.

{alphabet_instruction}

==================================================
EXACT FORMATTING STYLE (FOLLOW RIGIDLY)
==================================================

[RESOURCE HEADING] / [DESCRIPTOR]
(Example: Bamboo / rapidly renewable)

[DEFINITION PARAGRAPH]
Write a 1-paragraph summary explaining why this resource is a vital carbon sink or decarbonization tool. Use technical, evocative, and professional language.

[LISTINGS]
For each organization, research group, or product related to this resource:

[Firm or Group Name] [1-2 sentence description of their specific technical offering or research].

[STATUS]
(Use exactly one of these: Readily Available, In Development, Applied Research, Newly Deployed)

[REPEAT LISTINGS AS NEEDED]

See our listings for:
[Related resource type] / [Related descriptor]

==================================================
INPUT DATA
==================================================

TOPIC/QUERY: 
{query}

RESOURCE CATEGORY:
{resource_type}

KNOWLEDGE CONTEXT:
{context_str}

AUTHORITATIVE SOURCES FOR REFERENCE:
{sources}


"""
# After generating the content, add exactly:
# ---BEGIN EXPLANATION---
# Briefly explain which resource types were extracted and which sources/context informed the technical descriptions and statuses.
# ---END EXPLANATION---