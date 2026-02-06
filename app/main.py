from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from testing_module.prime_sperm import prime_sperm_auth


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


@app.post("/prime-sperm/auth")
async def prime_sperm_authtest(request: Request):
    """Health check endpoint."""

    request = await request.json()

    return prime_sperm_auth(
        email = request["email"], 
        product_key = request["product_key"],
        app_ssuid = request["app_ssuid"]
    )


if __name__ == "__main__":
    import uvicorn
    # Temporarily disable reload to avoid file watch limit error
    # To permanently fix, increase system inotify limit: sudo sysctl fs.inotify.max_user_watches=524288
    uvicorn.run("main:app", host="192.168.9.250", port=9090, reload=False)
