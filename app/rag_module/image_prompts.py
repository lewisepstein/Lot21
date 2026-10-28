import re

STYLE_PRESETS = {
    "photo": (
        "Professional, high-resolution environmental photography. "
        "Realistic lighting, natural materials, cinematic composition, "
        "human-scale context, climate-positive infrastructure."
    ),
    "aerial": (
        "Straight-down aerial photograph taken directly overhead (nadir, drone "
        "or satellite view). The camera points vertically at the ground: no "
        "horizon, no perspective, no oblique angle, no eye-level view. "
        "Realistic daylight, high resolution, photographic detail."
    ),
    "diagram": (
        "Clean technical diagram or infographic. "
        "Flat vector or isometric style, white or light background, "
        "clear labels, arrows, minimal color palette, engineering clarity."
    ),
    "editorial": (
        "Editorial illustration style. "
        "Soft textures, balanced composition, modern graphic design, "
        "subtle color gradients, publication-ready."
    )
}

# Applied to every image prompt: the client rejected galleries, title text,
# picture frames and invented source captions painted into the image.
IMAGE_RULES = (
    "Produce exactly ONE single image, not a collage, grid, gallery or set. "
    "Do not render any text, titles, captions, labels, URLs, watermarks or "
    "source lines inside the image. No picture frames, borders, mats, "
    "gallery walls or backgrounds around the image: the photograph fills the "
    "whole frame."
)

AERIAL_KEYWORDS = (
    "aerial", "overhead", "nadir", "bird's-eye", "birds-eye", "bird's eye",
    "top-down", "top down", "drone view", "satellite view", "from above",
)

DIAGRAM_KEYWORDS = (
    "diagram", "workflow", "process", "architecture",
    "how it works", "system", "flow", "chart", "schematic",
    "flowchart", "infographic",
)

ILLUSTRATION_KEYWORDS = (
    "illustration", "illustrated", "illustrate", "drawing", "painting",
    "watercolour", "watercolor", "sketch", "vector art", "line art",
    "flat colour", "flat color", "graphic style", "house style",
)


def _mentions(q: str, keywords) -> bool:
    """Whole-word match (plurals allowed): "flow" must not fire on "flowers"."""
    return any(re.search(rf"\b{re.escape(k)}(?:s|es)?\b", q) for k in keywords)


def detect_visual_mode(query: str, conversation_history=None) -> str:
    """Decide between a diagram, an illustration, a straight-down aerial photo, or a photo."""
    q = (query or "").lower()
    if _mentions(q, DIAGRAM_KEYWORDS):
        return "diagram"
    if _mentions(q, ILLUSTRATION_KEYWORDS):
        return "editorial"
    if _mentions(q, AERIAL_KEYWORDS):
        return "aerial"
    # A style set earlier in the session ("images must be directly overhead")
    # still applies to a plain follow-up. Diagram words are not carried: text
    # prompts often say "system" or "process" without wanting a diagram.
    # The most recent style instruction wins.
    for turn in reversed((conversation_history or [])[-3:]):
        earlier = (turn.get("prompt") or "").lower()
        if _mentions(earlier, ILLUSTRATION_KEYWORDS):
            return "editorial"
        if _mentions(earlier, AERIAL_KEYWORDS):
            return "aerial"
    return "photo"


def build_image_prompt(query, context, style_key="photo", conversation_history=None):
    """
    Compact, image-optimized prompt: the user's request first, standing
    instructions from earlier prompts in this session, truncated page context,
    the style preset, and the fixed output rules.
    """
    visual_context = (context or "")[:800]
    style_text = STYLE_PRESETS.get(style_key, STYLE_PRESETS["photo"])

    previous = ""
    if conversation_history:
        earlier = [t.get("prompt", "").strip() for t in conversation_history[-3:] if t.get("prompt")]
        if earlier:
            previous = (
                "\n\nPREVIOUS INSTRUCTIONS IN THIS SESSION (still apply):\n"
                + "\n".join(f"- {p}" for p in earlier)
            )

    return (
        f"Create a visual representation for the following topic.\n\n"
        f"TOPIC:\n{query}"
        f"{previous}\n\n"
        f"BACKGROUND CONTEXT:\n{visual_context}\n\n"
        f"STYLE:\n{style_text}\n\n"
        f"OUTPUT RULES:\n{IMAGE_RULES}"
    )
