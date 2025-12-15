"""
Weaviate RAG endpoints module.
Provides upload and query functionality for document chunking and retrieval.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
import uuid
import logging

from weaviate_module.weaviate_utils import (
    chunk_text,
    embed_texts_openai,
    build_rag_prompt,
    generate_answer_openai
)
from service_utils.db_utils.weaviate_db import WeaviateDB

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/weaviate", tags=["weaviate"])

# Constants
COLLECTION_NAME = "DocumentChunk"
EMBED_LOCALLY = False  # Set to True to compute embeddings locally


# Pydantic models
class UploadDoc(BaseModel):
    text: str
    source: Optional[str] = "user_text"
    doc_id: Optional[str] = None


class QueryIn(BaseModel):
    query: str
    top_k: Optional[int] = 4
    temperature: Optional[float] = 0.0


@router.post("/upload", summary="Upload raw text (one doc) and index into Weaviate")
async def upload(doc: UploadDoc):
    """
    Upload a document, chunk it, and index into Weaviate.
    
    Args:
        doc: Document with text, optional source and doc_id
        
    Returns:
        JSON with status, doc_id, and chunks_indexed count
    """
    if not doc.text or not doc.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    
    try:
        # Initialize Weaviate connection
        weaviate_db = WeaviateDB()
        
        # Ensure collection exists
        if not weaviate_db.collection_exists(COLLECTION_NAME):
            weaviate_db.create_collection(
                name=COLLECTION_NAME,
                description="Text chunks for RAG",
                properties=[
                    {"name": "text", "data_type": "text"},
                    {"name": "source", "data_type": "text"},
                    {"name": "chunk_index", "data_type": "int"},
                    {"name": "doc_id", "data_type": "text"},
                ],
                vectorizer="none"  # Use custom vectors or configure as needed
            )
        
        # Generate doc_id and chunk text
        doc_id = doc.doc_id or str(uuid.uuid4())
        chunks = chunk_text(doc.text)
        
        # Compute embeddings if needed
        vectors = None
        if EMBED_LOCALLY:
            vectors = embed_texts_openai(chunks)
        
        # Get collection and batch insert
        weaviate_db = WeaviateDB()
        collection = weaviate_db.get_collection(COLLECTION_NAME)
        
        if not collection:
            raise HTTPException(status_code=500, detail="Failed to get collection")
        
        # Batch insert chunks
        with collection.batch.dynamic() as batch:
            for idx, chunk in enumerate(chunks):
                properties = {
                    "text": chunk,
                    "source": doc.source,
                    "chunk_index": idx,
                    "doc_id": doc_id,
                }
                if EMBED_LOCALLY and vectors:
                    batch.add_object(properties=properties, vector=vectors[idx])
                else:
                    batch.add_object(properties=properties)
        
        logger.info(f"Indexed {len(chunks)} chunks for doc_id: {doc_id}")
        return {"status": "ok", "doc_id": doc_id, "chunks_indexed": len(chunks)}
        
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing error: {str(e)}")


@router.post("/query", summary="Run a query: retrieve top_k chunks and generate an answer")
async def query(q: QueryIn):
    """
    Query the vector database and generate an answer using RAG.
    
    Args:
        q: Query input with query text, top_k, and temperature
        
    Returns:
        JSON with answer, sources, and retrieved_count
    """
    try:
        # Initialize Weaviate and get collection
        weaviate_db = WeaviateDB()
        collection = weaviate_db.get_collection(COLLECTION_NAME)
        
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{COLLECTION_NAME}' not found")
        
        # Perform vector search
        response = collection.query.near_text(
            query=q.query,
            limit=q.top_k,
            return_properties=["text", "source", "chunk_index", "doc_id"]
        )
        
        hits = response.objects if hasattr(response, 'objects') else []
        
        if not hits:
            return {"answer": "", "sources": [], "retrieved_count": 0}
        
        # Build context and sources
        context_pieces = []
        sources = []
        for hit in hits:
            props = hit.properties
            txt = props.get("text", "")
            src = props.get("source", "unknown")
            idx = props.get("chunk_index", None)
            docid = props.get("doc_id", None)
            
            context_pieces.append(f"Source: {src} (doc:{docid} chunk:{idx})\n{txt}")
            sources.append({"source": src, "doc_id": docid, "chunk_index": idx})
        
        # Build RAG prompt
        context = "\n\n---\n\n".join(context_pieces)
        prompt = build_rag_prompt(context, q.query)
        
        # Generate answer using OpenAI
        answer = generate_answer_openai(prompt, q.temperature)
        
        return {"answer": answer, "sources": sources, "retrieved_count": len(hits)}
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")