import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField
)
from azure.search.documents.indexes.models import ComplexField
import os
from dotenv import load_dotenv

load_dotenv()

# Setup
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_NOTION_INDEX")
CHUNKS_FILE = "web_chunks.json"

# Creates index if it's not
def crear_indice_si_no_existe():
    index_client = SearchIndexClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY)
    )

    indices = [i.name for i in index_client.list_indexes()]
    if INDEX_NAME in indices:
        print(f"ℹ️ El índice '{INDEX_NAME}' ya existe.")
        return

    index = SearchIndex(
        name=INDEX_NAME,
        fields=[
            SimpleField(name="id", type="Edm.String", key=True),
            SearchableField(name="title", type="Edm.String", sortable=True),
            SearchableField(name="content", type="Edm.String"),
            ComplexField(
    name="metadata",
    fields=[
        SimpleField(name="source", type="Edm.String", filterable=True),
        SimpleField(name="filename", type="Edm.String", filterable=True),
        SimpleField(name="index", type="Edm.Int32", filterable=True, sortable=True)
    ]
)
        ]
    )

    index_client.create_index(index)
    print(f"✅ Índice '{INDEX_NAME}' creado.")

# Upload documents
def subir_documentos():
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY)
    )

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        documentos = json.load(f)

    resultado = search_client.upload_documents(documents=documentos)
    print(f"📤 {len(documentos)} documentos subidos.")
    print("📝 Resultado:", resultado)

if __name__ == "__main__":
    crear_indice_si_no_existe()
    subir_documentos()
