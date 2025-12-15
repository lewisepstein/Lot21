"""
Weaviate configuration module.
Contains connection settings for Weaviate vector database.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Weaviate connection settings
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", None)

# Optional authentication settings
WEAVIATE_AUTH_CONFIG = {}
if WEAVIATE_API_KEY:
    WEAVIATE_AUTH_CONFIG = {
        "api_key": WEAVIATE_API_KEY
    }
