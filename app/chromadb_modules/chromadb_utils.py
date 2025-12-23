import chromadb
from chromadb.config import Settings

client = chromadb.Client(
    Settings(
        persist_directory="./chroma_db",
        anonymized_telemetry=False
    )
)

collection = client.get_or_create_collection("lot21_docs")

collection.add(
    documents=["Chroma is working locally"],
    ids=["1"]
)

print(collection.query(
    query_texts=["working"],
    n_results=1
))
