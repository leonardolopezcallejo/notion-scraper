# app/chunker_with_embeddings.py
import os
import json
import uuid
from dotenv import load_dotenv
from typing import List
import tiktoken
from openai import AzureOpenAI

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

INPUT_FILE = "data/notion_extracted.txt"
OUTPUT_FILE = "data/notion_chunks_with_embeddings.json"
CHUNK_SIZE_TOKENS = 500       # Max tokens per chunk
CHUNK_OVERLAP_TOKENS = 50     # Overlap to keep context

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")  # Must be an embeddings model deployment

client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# -----------------------------
# Helper functions
# -----------------------------
def load_text() -> str:
    """Load full Notion extracted text file."""
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"File {INPUT_FILE} not found")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def tokenize_text(text: str) -> List[int]:
    """Convert text into token IDs."""
    encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
    return encoding.encode(text)

def detokenize(tokens: List[int]) -> str:
    """Convert token IDs back into text."""
    encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
    return encoding.decode(tokens)

def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split text into overlapping chunks."""
    tokens = tokenize_text(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_str = detokenize(chunk_tokens).strip()
        if chunk_str:
            chunks.append(chunk_str)
        start += chunk_size - overlap
    return chunks

def generate_embedding(text: str) -> List[float]:
    """Generate embedding vector using Azure OpenAI."""
    response = client.embeddings.create(
        input=text,
        model=AZURE_OPENAI_DEPLOYMENT
    )
    return response.data[0].embedding

# -----------------------------
# Main execution
# -----------------------------
if __name__ == "__main__":
    print("Loading extracted text...")
    full_text = load_text()

    print("Splitting into chunks...")
    chunks = chunk_text(full_text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
    print(f"✅ {len(chunks)} chunks generated.")

    documents = []
    for i, chunk in enumerate(chunks):
        print(f"🔹 Generating embedding {i+1}/{len(chunks)}...")
        embedding = generate_embedding(chunk)
        documents.append({
            "id": str(uuid.uuid4()),
            "content": chunk,
            "embedding": embedding,
            "metadata": {
                "source": "notion",
                "chunk_index": i
            }
        })

    print(f"Saving {len(documents)} chunks with embeddings...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    print(f"Done! Output saved to: {OUTPUT_FILE}")
