import importlib
import inspect

# The 40 routes to convert async def -> def (login_page in main.py is deliberately
# excluded to keep main.py untouched). Grouped by module.
CONVERTED = {
    "auth_module.auth": ["login", "logout", "password_reset", "password_change"],
    "category_module.category": ["create_category"],
    "content_module.content": ["create_content", "add_draft_content", "user_save_as_draft"],
    "content_module.prompt_history": [
        "get_prompt_history", "get_content_history", "restore_content_history_version",
        "set_action_prompt_history", "get_all_prompt_history",
    ],
    "dashboard_module.dashboard": ["dashboard_data"],
    "download_module.download_routes": [
        "download_content", "download_freeform_message", "download_category",
    ],
    "freeform_module.freeform": [
        "create_new_project", "list_projects", "get_project", "update_existing_project",
        "delete_existing_project", "get_project_chat_history", "send_chat_message",
    ],
    "page_modules.page": [
        "create_page", "get_page", "update_page_endpoint", "delete_page_record", "delete_pages",
    ],
    "agent_module.agent": [
        "get_api_credentials", "get_schedule_settings", "get_content_settings",
        "get_model_settings", "get_image_model_settings", "get_training_history_endpoint",
        "delete_training_record", "get_training_record_versions",
        "restore_training_record_version",
    ],
    "wordpress_module.wordpress_routes": ["publish_status", "list_published"],
}

# Must STAY async: real awaits (wordpress httpx, agent request.json()), require_session_auth
# wrappers (dashboard_page/page_content), and the deliberately-skipped main.login_page.
STILL_ASYNC = {
    "wordpress_module.wordpress_routes": ["publish_content", "unpublish_content", "test_wp_connection"],
    "agent_module.agent": ["save_api_credentials"],
    "dashboard_module.dashboard": ["dashboard_page"],
    "page_modules.page": ["page_content"],
    "main": ["login_page"],
}


def test_converted_routes_are_sync():
    for mod, names in CONVERTED.items():
        m = importlib.import_module(mod)
        for name in names:
            fn = getattr(m, name)
            assert not inspect.iscoroutinefunction(fn), f"{mod}.{name} should be def (sync)"


def test_excluded_routes_stay_async():
    for mod, names in STILL_ASYNC.items():
        m = importlib.import_module(mod)
        for name in names:
            fn = getattr(m, name)
            assert inspect.iscoroutinefunction(fn), f"{mod}.{name} must stay async"
