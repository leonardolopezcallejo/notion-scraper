# app_api.py
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Azure Search configuration
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-35-turbo")

if not all(
    [
        AZURE_SEARCH_ENDPOINT,
        AZURE_SEARCH_KEY,
        AZURE_SEARCH_INDEX,
        AZURE_OPENAI_ENDPOINT,
        AZURE_OPENAI_KEY,
        AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    ]
):
    raise RuntimeError("Missing required environment variables")

# FastAPI app
app = FastAPI(title="RAG Notion API")

# CORS for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Clients
search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=AZURE_SEARCH_INDEX,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY),
)

aoai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# Request and response models
class Pregunta(BaseModel):
    texto: str
    top_k: Optional[int] = 5
    hybrid: Optional[bool] = False
    max_context_chars: Optional[int] = 12000

class ChatRespuesta(BaseModel):
    respuesta: str

def embed_query(text: str) -> List[float]:
    """Create an embedding for the query using the configured embeddings deployment."""
    resp = aoai_client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        input=text,
    )
    return resp.data[0].embedding

def vector_search(question: str, top_k: int, hybrid: bool) -> List[Dict[str, Any]]:
    """Run vector or hybrid search on Azure AI Search and return hits."""
    q_vec = embed_query(question)
    vq = VectorizedQuery(vector=q_vec, k_nearest_neighbors=top_k, fields="contentVector")

    if hybrid:
        results = search_client.search(
            search_text=question,
            vector_queries=[vq],
            select=["id", "title", "content", "metadata"],
        )
    else:
        results = search_client.search(
            search_text=None,
            vector_queries=[vq],
            select=["id", "title", "content", "metadata"],
        )
    return list(results)

def build_context(hits: List[Dict[str, Any]], budget: int) -> str:
    """Concatenate passages under a character budget for the LLM prompt."""
    buf: List[str] = []
    used = 0
    for h in hits:
        chunk = h.get("content") or ""
        if not chunk:
            continue
        take = chunk[: max(0, budget - used)]
        if not take:
            break
        buf.append(take)
        used += len(take)
        if used >= budget:
            break
    return "\n\n".join(buf)

def answer_with_rag(question: str, context: str) -> str:
    """Call chat completion grounded on provided context."""
    system = (
        "You are a helpful assistant. Answer using only the provided context. "
        "If the answer is not present, say you do not know. Extend answers with examples if relevant."
    )
    user = f"Question:\n{question}\n\nContext:\n{context}"
    resp = aoai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

@app.get("/health")
def health():
    """Health endpoint to verify the service is up."""
    return {"status": "ok"}

@app.post("/chat", response_model=ChatRespuesta)
def chat(pregunta: Pregunta):
    """Main RAG endpoint. Returns only the final answer, no sources."""
    try:
        top_k = pregunta.top_k or 5
        hybrid = bool(pregunta.hybrid)
        max_ctx = pregunta.max_context_chars or 12000

        hits = vector_search(pregunta.texto, top_k, hybrid)
        context = build_context(hits, max_ctx)
        respuesta = answer_with_rag(pregunta.texto, context)

        return ChatRespuesta(respuesta=respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
