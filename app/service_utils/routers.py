"""
Router registration module.
Centralizes all router imports and registration logic.
"""

from fastapi import FastAPI

from auth_module.auth import router as auth_router
from dashboard_module.dashboard import router as dashboard_router
from projects_module.projects import router as projects_router
from resources_module.resources import router as resources_router
from content_module.content import router as content_router
from content_module.prompt_history import router as prompt_history_router
from category_module.category import router as category_router
from page_modules.page import router as page_router
from agent_module.agent import router as agent_router


def register_routers(app: FastAPI) -> None:
    """
    Register all application routers to the FastAPI app instance.
    
    Args:
        app: FastAPI application instance
    """
    app.include_router(auth_router, tags=["auth"])
    app.include_router(dashboard_router, tags=["user"])
    app.include_router(projects_router, tags=["user"])
    app.include_router(resources_router, tags=["user"])
    app.include_router(content_router, tags=["user"])
    app.include_router(prompt_history_router, tags=["user"])
    app.include_router(category_router, tags=["user"])
    app.include_router(page_router, tags=["user"])
    app.include_router(agent_router, tags=["user"])