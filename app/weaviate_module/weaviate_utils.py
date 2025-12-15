"""
Weaviate utility functions.
Provides text chunking, embedding, and RAG prompt generation utilities.
"""
import os
import tiktoken
import logging
from typing import List, Dict, Any

from service_utils.db_utils.weaviate_db import WeaviateDB

# Set up logging
logger = logging.getLogger(__name__)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Initialize OpenAI if available
if OPENAI_API_KEY:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
    except ImportError:
        logger.warning("openai package not installed")
        openai = None
else:
    openai = None

# Token encoding for chunking
ENCODING = "cl100k_base"  # tiktoken encoding for OpenAI models


def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> List[str]:
    """
    Chunk text into smaller pieces based on token count.
    
    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk (default: 400)
        overlap: Number of overlapping tokens between chunks (default: 50)
        
    Returns:
        List of text chunks
        
    Examples:
        >>> chunks = chunk_text("Long document text...", max_tokens=200)
        >>> print(f"Created {len(chunks)} chunks")
    """
    try:
        enc = tiktoken.get_encoding(ENCODING)
        toks = enc.encode(text)
        chunks = []
        i = 0
        while i < len(toks):
            chunk_toks = toks[i : i + max_tokens]
            chunk_text = enc.decode(chunk_toks)
            chunks.append(chunk_text)
            i += max_tokens - overlap
        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        # Fallback: simple character-based chunking
        chunk_size = max_tokens * 4  # Rough approximation
        overlap_chars = overlap * 4
        chunks = []
        i = 0
        while i < len(text):
            chunk = text[i : i + chunk_size]
            chunks.append(chunk)
            i += chunk_size - overlap_chars
        return chunks


def embed_texts_openai(texts: List[str], model: str = "text-embedding-3-small") -> List[List[float]]:
    """
    Compute OpenAI embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
        model: OpenAI embedding model (default: text-embedding-3-small)
        
    Returns:
        List of embedding vectors
        
    Raises:
        RuntimeError: If OPENAI_API_KEY is not configured
        
    Examples:
        >>> embeddings = embed_texts_openai(["text 1", "text 2"])
        >>> print(f"Generated {len(embeddings)} embeddings")
    """
    if not OPENAI_API_KEY or not openai:
        raise RuntimeError("OPENAI_API_KEY required for local embeddings and openai package must be installed.")
    
    try:
        resp = openai.Embedding.create(model=model, input=texts)
        return [d["embedding"] for d in resp["data"]]
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise RuntimeError(f"Embedding generation failed: {e}")


def build_rag_prompt(context: str, query: str) -> str:
    """
    Build a RAG (Retrieval Augmented Generation) prompt.
    
    Args:
        context: Retrieved context from vector database
        query: User's query
        
    Returns:
        Formatted prompt string
        
    Examples:
        >>> prompt = build_rag_prompt("Context text...", "What is...?")
    """
    prompt = (
        "You are a helpful assistant. Use ONLY the information in CONTEXT to answer the question. "
        "If the answer is not contained in the context, say 'I don't know'.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {query}\n\n"
        "Answer concisely and include citations like [source: source_name]."
    )
    return prompt


def generate_answer_openai(prompt: str, temperature: float = 0.0, max_tokens: int = 400) -> str:
    """
    Generate an answer using OpenAI's chat completion API.
    
    Args:
        prompt: The prompt to send to the model
        temperature: Sampling temperature (default: 0.0)
        max_tokens: Maximum tokens in response (default: 400)
        
    Returns:
        Generated answer text
        
    Examples:
        >>> answer = generate_answer_openai("What is...?", temperature=0.7)
    """
    if not OPENAI_API_KEY or not openai:
        logger.warning("OPENAI_API_KEY not configured")
        return f"No OPENAI_API_KEY configured. Here is the assembled context; call your LLM with it.\n\n{prompt}"
    
    try:
        gen = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Change as needed
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        answer = gen["choices"][0]["message"]["content"].strip()
        return answer
    except Exception as e:
        logger.error(f"LLM generation error: {e}")
        raise RuntimeError(f"LLM generation failed: {e}")


def load_chunks_to_weaviate(
    chunks: List[str],
    collection_name: str,
    doc_id: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Load text chunks into Weaviate vector database.
    
    Args:
        chunks: List of text chunks to load
        collection_name: Name of the Weaviate collection
        doc_id: Unique document identifier
        description: Optional description for the collection
        
    Returns:
        Dictionary with success status, collection name, and chunks created
        
    Raises:
        RuntimeError: If Weaviate operations fail
        
    Examples:
        >>> chunks = ["chunk1", "chunk2", "chunk3"]
        >>> result = load_chunks_to_weaviate(
        ...     chunks,
        ...     "my_collection",
        ...     "doc-123",
        ...     description="Training data"
        ... )
        >>> print(f"Loaded {result['chunks_created']} chunks")
    """
    try:
        # Initialize Weaviate connection
        weaviate_db = WeaviateDB()
        client = weaviate_db.client
        
        # Ensure collection exists
        if not client.collections.exists(collection_name):
            logger.info(f"Creating new collection: {collection_name}")
            weaviate_db.create_collection(
                name=collection_name,
                description=description or "Training data collection",
                properties=[
                    {"name": "text", "data_type": "text"},
                    {"name": "source", "data_type": "text"},
                    {"name": "chunk_index", "data_type": "int"},
                    {"name": "doc_id", "data_type": "text"},
                ],
                vectorizer="none"  # Use custom vectors or configure as needed
            )
        
        chunks_count = len(chunks)
        logger.info(f"Loading {chunks_count} chunks into collection '{collection_name}'")
        
        # Get collection for batch insert
        collection = client.collections.get(collection_name)
        
        # Batch insert chunks into Weaviate
        logger.info("Inserting chunks into Weaviate...")
        with collection.batch.dynamic() as batch:
            for idx, chunk in enumerate(chunks):
                properties = {
                    "text": chunk,
                    "source": "agent_training_data",
                    "chunk_index": idx,
                    "doc_id": doc_id,
                }
                batch.add_object(properties=properties)
        
        logger.info(f"Successfully loaded {chunks_count} chunks into collection '{collection_name}'")
        
        return {
            "success": True,
            "chunks_created": chunks_count,
            "collection_name": collection_name,
            "doc_id": doc_id
        }
        
    except Exception as e:
        logger.error(f"Failed to load chunks to Weaviate: {str(e)}")
        raise RuntimeError(f"Failed to load chunks to Weaviate: {str(e)}")


def delete_chunks_from_weaviate(
    collection_name: str,
    doc_id: str
) -> Dict[str, Any]:
    """
    Delete all chunks with a specific doc_id from Weaviate collection.
    
    Args:
        collection_name: Name of the Weaviate collection
        doc_id: Unique document identifier to delete
        
    Returns:
        Dictionary with success status and number of chunks deleted
        
    Raises:
        RuntimeError: If Weaviate operations fail
        
    Examples:
        >>> result = delete_chunks_from_weaviate("my_collection", "doc-123")
        >>> print(f"Deleted {result['chunks_deleted']} chunks")
    """
    try:
        # Initialize Weaviate connection
        weaviate_db = WeaviateDB()
        client = weaviate_db.client
        
        # Check if collection exists
        if not client.collections.exists(collection_name):
            logger.warning(f"Collection '{collection_name}' does not exist")
            return {
                "success": True,
                "chunks_deleted": 0,
                "message": f"Collection '{collection_name}' does not exist"
            }
        
        # Get collection
        collection = client.collections.get(collection_name)
        
        logger.info(f"Deleting chunks with doc_id '{doc_id}' from collection '{collection_name}'")
        
        # Delete all objects with matching doc_id
        result = collection.data.delete_many(
            where={
                "path": ["doc_id"],
                "operator": "Equal",
                "valueText": doc_id
            }
        )
        
        deleted_count = result.successful if hasattr(result, 'successful') else 0
        
        logger.info(f"Successfully deleted {deleted_count} chunks from collection '{collection_name}'")
        
        return {
            "success": True,
            "chunks_deleted": deleted_count,
            "collection_name": collection_name,
            "doc_id": doc_id
        }
        
    except Exception as e:
        logger.error(f"Failed to delete chunks from Weaviate: {str(e)}")
        raise RuntimeError(f"Failed to delete chunks from Weaviate: {str(e)}")
