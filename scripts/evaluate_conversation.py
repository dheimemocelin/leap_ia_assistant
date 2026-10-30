"""Offline synthetic dialogue replay; never invokes a real LLM."""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

from app.agent.llm import ModelReply, ToolCall
from app.api.chat import build_agent


class OfflineModel:
    async def complete(self, messages, tools):
        if tools:
            return ModelReply(tool_calls=[ToolCall(name="list_vehicles")])
        if "variants" in messages[-1]["content"]:
            return ModelReply(text='{"variant":1}')
        evidence = json.loads(messages[-1]["content"].split(": ", 1)[1])
        if evidence.get("kind") == "get_vehicle_details":
            return ModelReply(
                text=json.dumps({"fact_ids": [f["id"] for f in evidence.get("facts", [])]})
            )
        return ModelReply(text="Posso apresentar os modelos B10 e C10.")


SDR_DIALOGUE = [
    "Qual a autonomia do C10 BEV?",
    "Manda fotos.",
    "Pensei em utilizar para Uber.",
    "Uso com minha família também",
    "Nunca tive um elétrico",
    "Tenho dúvidas sobre recarga",
    "Agora quero ver B10 REEV",
    "Quero conhecer presencialmente",
    "Não quero falar com vendedor",
]

CONSULTATIVE_DIALOGUE = [
    "Olá",
    "Tenho interesse no B10",
    "BEV",
    "Uso mais na cidade",
    "Tenho dois filhos e preciso de espaço",
    "Tenho receio de um carro elétrico",
    "Quero conhecer o carro presencialmente",
    "Não quero contato",
    "Qual o preço?",
    "Agora quero ver o C10 BEV",
]


SCREENSHOT_DIALOGUE = [
    "oi",
    "Pessoa Sintetica",
    "o b10",
    "reev",
    "bom é pra viagem e economia",
    "uns 500 km",
    "em casa",
]
SDR_V2_DIALOGUE = [
    "oi",
    "Me chamo Pessoa Sintetica",
    "o B10",
    "BEV",
    "Pensei em utilizar para Uber.",
    "Uns 200 km",
    "Uso com a família também",
    "Nunca tive um elétrico",
    "Tenho dúvidas sobre recarga",
    "Em casa",
    "Qual o preço?",
    "Quero conhecer presencialmente",
    "Não quero falar com vendedor",
    "Agora quero C10 BEV",
    "Qual a autonomia?",
    "Quero falar com um consultor",
    "sim",
    "11000000000",
]


async def replay(dialogue):
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = OfflineModel()
    rows = []
    for text in dialogue:
        response = await agent.turn("synthetic-replay", text)
        state = agent.sessions[("local", "synthetic-replay")]
        rows.append(
            {
                "user": text,
                "assistant": response.model_dump(mode="json"),
                "usage": state["usage"],
                "profile": state.get("lead_profile", {}),
            }
        )
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=["consultative", "sdr", "screenshot", "sdr-v2"],
        default="consultative",
    )
    parser.add_argument("--implementation-label", default="working-tree")
    args = parser.parse_args()
    payload = {
        "baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "synthetic": True,
        "implementation": args.implementation_label,
        "real_llm_calls": 0,
        "scenario": args.scenario,
        "turns": asyncio.run(
            replay(
                {
                    "sdr": SDR_DIALOGUE,
                    "consultative": CONSULTATIVE_DIALOGUE,
                    "screenshot": SCREENSHOT_DIALOGUE,
                    "sdr-v2": SDR_V2_DIALOGUE,
                }[args.scenario]
            )
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
