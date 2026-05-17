import argparse
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.7,
    max_tokens=1024,
    timeout=30,
)

SYSTEM = (
    "Você é um assistente de análise financeira. "
    "Responda de forma clara e objetiva."
)


def pergunta(texto: str) -> str:
    resposta = llm.invoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=texto),
    ])
    return resposta.content


def chat():
    print("🤖 Assistente iniciado! Digite 'sair' para encerrar.\n")
    while True:
        user = input("Você: ").strip()
        if user.lower() == "sair":
            print("Até logo!")
            break
        if not user:
            continue
        print(f"Assistente: {pergunta(user)}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", help="Pergunta para resposta única")
    args = parser.parse_args()

    if args.message:
        print(pergunta(args.message))
    else:
        chat()
