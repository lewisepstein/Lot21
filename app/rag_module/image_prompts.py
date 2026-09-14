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
)


def detect_visual_mode(query: str) -> str:
    """Decide between a diagram, a straight-down aerial photo, or a photo."""
    q = (query or "").lower()
    if any(k in q for k in DIAGRAM_KEYWORDS):
        return "diagram"
    if any(k in q for k in AERIAL_KEYWORDS):
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
