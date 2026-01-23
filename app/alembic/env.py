from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

import sys
from pathlib import Path
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# -------------------------------------------------------
# Load environment variables from .env file
# -------------------------------------------------------
# Navigate to the parent directory where .env should be located
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Try loading from current directory as fallback
    load_dotenv()

# -------------------------------------------------------
# Path setup – allow importing app models
# -------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.base import metadata

from models import (
    User,
    Category,
    Page,
    Scheduler,
    Task,
    TaskRun,
    Content,
    PromptHistory,
    TaskProcess,
    WeaviateData,
    Session,
    WeaviateDataVersion,
    PromptAttachments,
)

# -------------------------------------------------------
# Alembic config & logging
# -------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata

# -------------------------------------------------------
# Build DATABASE_URL safely (NO configparser involved)
# -------------------------------------------------------
required_env_vars = ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST', 'POSTGRES_DB']
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

if missing_vars:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing_vars)}. "
        f"Please ensure your .env file is properly configured."
    )

password = quote_plus(os.environ["POSTGRES_PASSWORD"])

DATABASE_URL = (
    f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:"
    f"{password}@{os.environ['POSTGRES_HOST']}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ['POSTGRES_DB']}"
)

# -------------------------------------------------------
# Offline migrations
# -------------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -------------------------------------------------------
# Online migrations
# -------------------------------------------------------
def run_migrations_online() -> None:
    engine = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# -------------------------------------------------------
# Entry point
# -------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
