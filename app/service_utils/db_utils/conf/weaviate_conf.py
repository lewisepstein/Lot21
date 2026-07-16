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

# Embedding settings for hybrid search. Weaviate reaches Ollama over the
# docker-compose network, so the endpoint uses the compose service name.
WEAVIATE_OLLAMA_ENDPOINT = os.getenv("WEAVIATE_OLLAMA_ENDPOINT", "http://ollama:11434")
WEAVIATE_EMBED_MODEL = os.getenv("WEAVIATE_EMBED_MODEL", "nomic-embed-text")

# Optional authentication settings
WEAVIATE_AUTH_CONFIG = {}
if WEAVIATE_API_KEY:
    WEAVIATE_AUTH_CONFIG = {"api_key": WEAVIATE_API_KEY}
