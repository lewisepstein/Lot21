from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env into environment

POSTGRES_HOST = os.getenv('POSTGRES_HOST', '192.168.9.177')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '123')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'lot21_db')

POSTGRES_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)