"""Interactive local terminal client: python3 -m app.cli --reviewed-catalog."""

import argparse
import asyncio

from app.api.chat import build_agent
from app.domain.response import AssistantResponse


async def converse(reviewed_catalog: bool):
    try:
        agent = build_agent(reviewed_catalog=reviewed_catalog, test_media=reviewed_catalog)
    except (ValueError, OSError):
        print("Não foi possível iniciar. Confira LLM_PROVIDER, LLM_MODEL e a chave no .env.")
        return
    print("LEAP — conversa no terminal")
    print("Digite /nova para reiniciar ou /sair para encerrar. Não informe dados pessoais.")
    if reviewed_catalog:
        print("Catálogo interno com informações verificadas e fotos autorizadas para teste.")
    else:
        print("Catálogo de atendimento em revisão: dados e fotos pendentes ficam bloqueados.")
    conversation = 1
    while True:
        try:
            text = input("\nVocê: ").strip()
        except EOFError:
            print("\nAté logo!")
            break
        if text.casefold() in {"/sair", "sair", "exit", "quit"}:
            print("Até logo!")
            break
        if text.casefold() == "/nova":
            conversation += 1
            print("Nova conversa iniciada.")
            continue
        if not text:
            continue
        if len(text) > 4000:
            print("LEAP: Use uma mensagem de até 4000 caracteres.")
            continue
        try:
            response = await agent.turn(f"terminal-{conversation}", text, owner="local-terminal")
            # Force the same mandatory commercial serialization used by the backend.
            safe = AssistantResponse.model_validate_json(response.model_dump_json())
            print("\nLEAP: " + safe.text)
            if safe.source_ids:
                print("Fontes: " + ", ".join(safe.source_ids))
            if safe.media_ids:
                print("Imagens: " + ", ".join(safe.media_ids))
        except Exception:  # noqa: BLE001 - never expose provider errors or credentials
            print("LEAP: Não consegui responder agora. Tente novamente ou digite /nova.")


def main():
    parser = argparse.ArgumentParser(
        description="Converse com o LEAP pelo terminal; pode consumir cota LLM."
    )
    parser.add_argument(
        "--reviewed-catalog",
        action="store_true",
        help="Usar fatos internos verificados, sem aprovar fotos reais",
    )
    args = parser.parse_args()
    try:
        asyncio.run(converse(args.reviewed_catalog))
    except KeyboardInterrupt:
        print("\nAté logo!")


if __name__ == "__main__":
    main()
