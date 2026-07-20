import json
from pathlib import Path

BASELINE = Path(__file__).parent / "baseline" / "route_inventory.json"


def _inventory(app):
    # OpenAPI paths are the canonical served-route list (handles FastAPI 0.139's
    # included-router wrapping, which flat app.routes enumeration does not).
    paths = app.openapi().get("paths", {})
    return {p: sorted(m.upper() for m in methods) for p, methods in paths.items()}


def test_route_inventory_unchanged(app):
    current = _inventory(app)
    if not BASELINE.exists():
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True))
    expected = json.loads(BASELINE.read_text())
    assert current == expected, "Route set (paths/methods) changed — investigate."
