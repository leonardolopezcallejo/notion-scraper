import uuid
import json
import os

CHUNK_SIZE = 800  # words
INPUT_FILE = "notion_contenido.txt"
OUTPUT_FILE = "notion_chunks.json"

def dividir_en_chunks(texto, max_palabras):
    palabras = texto.split()
    print(f"🔍 Total de palabras encontradas: {len(palabras)}")

    chunks = []
    while palabras:
        chunk = palabras[:max_palabras]
        palabras = palabras[max_palabras:]
        chunks.append(" ".join(chunk))

    print(f"✅ {len(chunks)} chunks generados.")
    return chunks

def preparar_documentos(texto):
    chunks = dividir_en_chunks(texto, CHUNK_SIZE)
    documentos = []

    for i, chunk in enumerate(chunks):
        doc = {
            "id": str(uuid.uuid4()),
            "title": f"Fragmento {i+1}",
            "content": chunk,
            "metadata": {
                "source": "notion",
                "filename": INPUT_FILE,
                "index": i
            }
        }
        documentos.append(doc)

    return documentos

if __name__ == "__main__":
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Archivo '{INPUT_FILE}' no encontrado.")
        exit()

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        texto = f.read()

    if not texto.strip():
        print("⚠️ El archivo está vacío.")
        exit()

    documentos = preparar_documentos(texto)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(documentos, f, indent=2, ensure_ascii=False)

    print(f"✅ {len(documentos)} documentos guardados en '{OUTPUT_FILE}'")
