import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

# Loads .env
load_dotenv()

# Azure Search
search_client = SearchClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name=os.getenv("AZURE_SEARCH_NOTION_INDEX"),
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
)

# Azure OpenAI
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2023-07-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")


def buscar_contexto(pregunta, top_k=3):
    resultados = search_client.search(pregunta, top=top_k)
    print("🔍 Usando índice:", os.getenv("AZURE_SEARCH_NOTION_INDEX"))

    return "\n\n".join([r["content"] for r in resultados])


def ask_with_rag_notion(pregunta):
    contexto = buscar_contexto(pregunta)

    prompt = f"""
Usa exclusivamente la siguiente información para responder a la pregunta. 
Si no está contenida aquí, responde correctamente pero empezando por "En la informacion dada, no hay nada sobre lo que preguntas pero..."".

Contexto:
{contexto}

Pregunta:
{pregunta}
"""

    respuesta = client.chat.completions.create(
        model=openai_deployment,
        messages=[
            {"role": "system", "content": "Eres un asistente experto que responde solo con el contexto dado y en los casos que use información de fuera del contexto, lo avisa"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )

    print("\n🧠 Respuesta:")
    print(respuesta.choices[0].message.content)

    return respuesta.choices[0].message.content



if __name__ == "__main__":
    while True:
        pregunta = input("\n❓ Introduce tu pregunta (o 'exit'): ")
        if pregunta.lower() in ["exit", "salir", "quit"]:
            break
        ask_with_rag_notion(pregunta)
