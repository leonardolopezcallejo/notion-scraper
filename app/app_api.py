from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ask_with_rag_notion import ask_with_rag_notion

app = FastAPI()

# Allows requests from browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class Pregunta(BaseModel):
    texto: str

@app.post("/chat")
def chat(pregunta: Pregunta):
    respuesta = preguntar_con_rag(pregunta.texto)
    print(f"➡️ Pregunta recibida: {pregunta}")
    print(f"⬅️ Respuesta generada: {respuesta}")
    return {"respuesta": respuesta}
