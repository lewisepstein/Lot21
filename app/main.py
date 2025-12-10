from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

from auth_module.auth import router as auth_router
from dashboard_module.dashboard import router as dashboard_router


# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Lottie", version="1.0.0")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Register routers
app.include_router(auth_router, tags=["auth"])
app.include_router(dashboard_router, tags=["user"])


# Default route - Login page
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Render login page."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error}
    )


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
