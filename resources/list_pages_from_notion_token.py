from notion_client import Client
import os
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
notion = Client(auth=NOTION_TOKEN)

def list_pages():
    print("🔍 Buscando páginas visibles para esta integración...\n")

    resultados = notion.search(
        filter={"value": "page", "property": "object"},
        page_size=1000  # increase in case of need
    )

    for r in resultados["results"]:
        titulo = ""
        propiedades = r.get("properties", {})
        nombre = r.get("object", "")

        if "title" in r.get("properties", {}):
            titulo = r["properties"]["title"]["title"][0]["plain_text"]
        elif "Name" in propiedades and propiedades["Name"]["type"] == "title":
            titulo = propiedades["Name"]["title"][0]["plain_text"]
        elif "title" in r:
            titulo = r["title"][0]["plain_text"] if r["title"] else ""
        
        print(f"🧾 Título: {titulo}")
        print(f"🆔 ID: {r['id']}")
        print(f"🔹 Tipo: {r['object']}")
        print("-" * 40)

if __name__ == "__main__":
    list_pages()
