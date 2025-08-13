# app/upload_to_azure_search_notion.py
import os
import json
import time
from typing import List, Optional
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError, ServiceResponseError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    ComplexField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration
)

# Load environment
load_dotenv()

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX")
CHUNKS_FILE = os.path.join("data", "notion_chunks_with_embeddings.json")

def detect_embedding_dim(path: str) -> int:
    """Detect embedding dimension from the first document that has an embedding."""
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    for d in docs:
        emb = d.get("embedding") or d.get("contentVector")
        if emb and isinstance(emb, list) and len(emb) > 0:
            return len(emb)
    raise ValueError("Could not detect embedding dimension from file. No 'embedding' or 'contentVector' found.")

def current_index_vector_dim(index_client: SearchIndexClient, index_name: str) -> Optional[int]:
    """Return the vector dimension of contentVector field in the existing index, or None if not found."""
    idx = index_client.get_index(index_name)
    for f in idx.fields:
        if getattr(f, "name", None) == "contentVector":
            # In this SDK, vector dimension is stored as vector_search_dimensions
            return getattr(f, "vector_search_dimensions", None)
    return None

def ensure_index(index_client: SearchIndexClient, embedding_dim: int) -> None:
    """Ensure index exists with the given embedding dimension. Recreate if mismatch."""
    existing = [i.name for i in index_client.list_indexes()]
    if INDEX_NAME in existing:
        try:
            dim = current_index_vector_dim(index_client, INDEX_NAME)
        except Exception:
            dim = None
        if dim is not None and dim != embedding_dim:
            print(f"Index '{INDEX_NAME}' has vector dim {dim} but data requires {embedding_dim}. Recreating index.")
            index_client.delete_index(INDEX_NAME)
        else:
            print(f"Index '{INDEX_NAME}' already exists with compatible schema.")
            return

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[VectorSearchProfile(name="vector-profile", algorithm_configuration_name="hnsw-config")]
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String, sortable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            ComplexField(
                name="metadata",
                fields=[
                    SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="index", type=SearchFieldDataType.Int32, filterable=True, sortable=True)
                ]
            ),
            SearchField(
                name="contentVector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=embedding_dim,
                vector_search_profile_name="vector-profile"
            )
        ],
        vector_search=vector_search
    )
    index_client.create_index(index)
    print(f"Index '{INDEX_NAME}' created with vector dim {embedding_dim}.")

def load_and_transform_documents(path: str, expected_dim: int) -> List[dict]:
    """Load JSON and map fields to the index schema. Skip documents with wrong vector size."""
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    transformed = []
    skipped = 0
    for d in docs:
        content = d.get("content") or ""
        title = d.get("title") or ""
        emb = d.get("embedding") or d.get("contentVector")
        if not emb or not isinstance(emb, list) or len(emb) != expected_dim:
            skipped += 1
            continue

        meta_in = d.get("metadata") or {}
        doc = {
            "id": d.get("id"),
            "title": title,
            "content": content,
            "contentVector": emb,
            "metadata": {
                "source": meta_in.get("source", "notion"),
                "filename": meta_in.get("filename", os.path.basename(path)),
                "index": meta_in.get("index", meta_in.get("chunk_index", 0))
            }
        }
        transformed.append(doc)

    if skipped:
        print(f"Skipped {skipped} documents due to vector size mismatch.")
    return transformed

def chunk_iter(items: List[dict], size: int):
    """Yield successive chunks of given size."""
    for i in range(0, len(items), size):
        yield items[i:i + size]

def upload_in_batches(search_client: SearchClient, documents: List[dict], initial_batch_size: int = 100) -> None:
    """Upload documents in batches with payload controls and basic retries."""
    total = len(documents)
    if total == 0:
        print("No documents to upload.")
        return

    batch_size = initial_batch_size
    i = 0
    while i < total:
        end = min(i + batch_size, total)
        batch = documents[i:end]
        try:
            search_client.upload_documents(documents=batch)
            print(f"Uploaded {len(batch)} documents [{i}-{end-1}].")
            i = end
            time.sleep(0.05)
        except HttpResponseError as e:
            msg = str(e)
            if getattr(e, "status_code", None) == 413 or "Too Large" in msg:
                if batch_size > 1:
                    batch_size = max(1, batch_size // 2)
                    print(f"Payload too large. Reducing batch size to {batch_size} and retrying.")
                    continue
                else:
                    print(f"Skipping one oversize document id={batch[0].get('id')}.")
                    i = end
                    continue
            if getattr(e, "status_code", None) in (429, 502, 503):
                print(f"Transient error {getattr(e, 'status_code', None)}. Retrying batch [{i}-{end-1}] after backoff.")
                time.sleep(1.0)
                continue
            raise
        except (ServiceRequestError, ServiceResponseError) as e:
            print(f"Transport error: {e}. Retrying batch [{i}-{end-1}] after backoff.")
            time.sleep(1.0)
            continue

if __name__ == "__main__":
    # Diagnostics
    try:
        import azure.search.documents as _asd
        print("azure-search-documents version:", getattr(_asd, "__version__", "unknown"))
    except Exception:
        pass
    print("Using chunks file:", CHUNKS_FILE)
    print("Script file path:", __file__)

    # Detect data dimension and ensure index
    embedding_dim = detect_embedding_dim(CHUNKS_FILE)
    print(f"Detected embedding dimension: {embedding_dim}")
    index_client = SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
    ensure_index(index_client, embedding_dim)

    # Load docs and upload
    docs = load_and_transform_documents(CHUNKS_FILE, embedding_dim)
    print(f"Prepared {len(docs)} documents for upload.")
    search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
    upload_in_batches(search_client, docs, initial_batch_size=100)
