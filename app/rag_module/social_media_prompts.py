from rag_module.prompt_rules import LottiePrompts

def build_social_media_post_prompt(
    topic: str = None,
    context_str: str = None,
    platform: str = "linkedin",
    tone: str = "informative",
    length: str = "medium"
) -> str:
    """
    Build a refined prompt for generating a single copy-paste ready social media post.
    
    Optimized for:
    - High-impact "hooks" and visual pacing (double line breaks).
    - Mandatory inclusion of authoritative sources at the end.
    - No source attribution inside the narrative (maintains professional flow).
    - Mandatory automatic hashtag generation (6-10).
    - No emojis or markdown (institutional style).
    """

    if not context_str:
        context_str = "No extra context provided."

    if not topic:
        topic = "the topic from the provided context"

    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

TASK:
You are a senior social copywriter for Lot21. Generate a single, high-impact social media post for `{platform}` based on the CONTEXT provided. 

STRICT CONTENT RULES:
1. NO NARRATIVE SOURCING: Do NOT mention where the information came from within the body of the post. Avoid phrases like "According to the context...", "Research shows...", or citing authors like "Robert Hoglund" inside the paragraphs.
2. THE HOOK: The first sentence must be a high-impact "hook" designed to grab the reader's attention immediately.
3. VISUAL PACING: Use double line breaks between short paragraphs (1-3 sentences each). Ensure there is plenty of white space for mobile readability.
4. DIRECTLY POSTABLE: The output must be a cohesive block including the caption, CTA, hashtags, and sources.
5. MANDATORY HASHTAGS: The post MUST conclude with a block of 6-10 relevant hashtags starting with #.
6. MANDATORY SOURCES: At the very end of the post content, list the names and URLs of the authoritative sources used under the label "SOURCES".
7. NO MARKDOWN/EMOJIS: Use ONLY plain text. No bold (**), no italics (*), and no emojis.

USER TOPIC: {topic}
TONE: {tone}
LENGTH: {length}

OUTPUT STRUCTURE:
[High-impact Hook Line]

[Body Paragraph 1 - facts/insight]

[Body Paragraph 2 - significance]

[The CTA sentence]

[6-10 Relevant Hashtags starting with #]

SOURCES
[List names of organizations/reports and URLs from the context]

--------------------------------------------------
(After each post, provide the following for internal use only)
IMAGE_ALT_TEXT: [One line descriptive alt text for the post image]

CONTEXT:
{context_str}

END
"""


def build_social_media_campaign_prompt(
    headline: str,
    key_points: list,
    audience: str = "general",
    platforms: list = None,
    tone: str = "informative",
) -> str:
    """
    Build a higher-level campaign prompt for a copy-paste ready 2-week strategy.
    Generates exactly one high-impact post per platform with integrated sources.
    """

    platforms = platforms or ["linkedin", "x"]
    points_text = "\n".join([f"- {p}" for p in (key_points or [])])

    return f"""{LottiePrompts.GUARDRAIL_RULES}

{LottiePrompts.PLAIN_TEXT_RULES}

TASK:
You are a senior social strategist for Lot21. Using the HEADLINE and KEY POINTS below, produce a campaign including one high-impact post per platform.

STRICT CONTENT RULES:
1. NO NARRATIVE SOURCING: Keep the post body focused on insights, not internal credits or author names.
2. HIGH-IMPACT HOOKS: Start every post with a compelling opening line.
3. WHITE SPACE: Ensure posts use double line breaks between paragraphs for readability.
4. MANDATORY SOURCES: Every post generated for a platform MUST include a "SOURCES" section at the bottom listing URLs or reports mentioned in the key points.
5. COPY-PASTE READY: Post content must be ready to publish immediately with CTA, Hashtags, and Sources integrated.

HEADLINE:
{headline}

KEY POINTS:
{points_text}

AUDIENCE: {audience}
TONE: {tone}

STRUCTURE:
1. For each platform in {platforms}: One cohesive post block (Hook + Body + CTA + Hashtags + Sources).
2. Suggested 2-week posting schedule (days and short rationale).
3. Creative brief: one-sentence guidance for imagery and one alt-text example per platform.

STRICT POST FORMAT:
[HIGH-IMPACT HOOK]

[BODY PARAGRAPHS WITH WHITE SPACE]

[CTA]

[6-10 HASHTAGS]

SOURCES
[Authoritative URLs or Report Names]

END
"""