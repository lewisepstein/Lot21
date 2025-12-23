from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


from service_utils.routers import register_routers
from service_utils.log_management import setup_logger

# Initialize logging
logger = setup_logger(__name__)
logger.info("Starting Lottie application...")

# Initialize FastAPI app
app = FastAPI(title="Lottie", version="1.0.0")

# Setup templates
templates = Jinja2Templates(directory="templates")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

# Register routers
register_routers(app)


# Default route - Login page
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Render login page."""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
