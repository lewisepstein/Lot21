STYLE_PRESETS = {
    "photo": (
        "Professional, high-resolution environmental photography. "
        "Realistic lighting, natural materials, cinematic composition, "
        "human-scale context, climate-positive infrastructure."
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

def detect_visual_mode(query: str) -> str:
    """
    Decide whether to generate a diagram or a photo.
    """
    diagram_keywords = {
        "diagram", "workflow", "process", "architecture",
        "how it works", "system", "flow", "chart", "schematic"
    }

    q = query.lower()
    if any(k in q for k in diagram_keywords):
        return "diagram"

    return "photo"


def build_image_prompt(query, context, style_key="photo"):
    """
    Builds a compact, image-optimized prompt using:
    - query
    - truncated context
    - explicit style preset
    """
    visual_context = (context or "")[:800]

    style_text = STYLE_PRESETS.get(style_key, STYLE_PRESETS["photo"])

    return (
        f"Create a visual representation for the following topic.\n\n"
        f"TOPIC:\n{query}\n\n"
        f"BACKGROUND CONTEXT:\n{visual_context}\n\n"
        f"STYLE:\n{style_text}"
    )
