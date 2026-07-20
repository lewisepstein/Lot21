import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# --- must run before importing app.main ---
# postgres_db_conf.py and auth_utils.py read these at import time; int(os.getenv(...))
# would crash on None. python-dotenv's load_dotenv() does not override already-set vars,
# so these test values win.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "lottie_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-prod")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("SESSION_EXPIRE_MINS", "60")

# main.py uses relative StaticFiles(directory="static") / Jinja2Templates(directory="templates"),
# so the app can only be imported with cwd = app/.
os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))


@pytest.fixture(scope="session")
def app():
    from main import app as fastapi_app

    return fastapi_app


@pytest_asyncio.fixture
async def client(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
