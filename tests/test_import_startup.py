def test_app_openapi_has_feature_routes(app):
    # Importing app.main mounts every router; a syntax/import error anywhere fails here.
    # FastAPI 0.139 wraps included routers, so enumerate via the OpenAPI schema
    # (the canonical served-path list) rather than flat app.routes.
    paths = app.openapi().get("paths", {})
    assert "/auth/login" in paths
    assert len(paths) > 50
