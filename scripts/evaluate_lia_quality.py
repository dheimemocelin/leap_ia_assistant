"""Offline structural evaluation, not a measurement of real-model naturalness."""

import argparse
import asyncio
import hashlib
import inspect
import json
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

from app.agent.llm import ModelReply, ToolCall
from app.api.chat import build_agent
from app.policy.commercial import CommercialPolicyEngine

SOCIAL_REFERENCE = {
    "que legal", "gostei", "gostei bastante", "muito bonito", "achei muito bonito",
    "interessante", "interessante mesmo", "nao gostei", "tenho duvidas",
    "quero saber mais", "ok", "obrigado", "entendi", "amei",
}


def is_reference_social(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)).strip("!.? ") in SOCIAL_REFERENCE


def summarize(dialogues):
    turns = [t for d in dialogues for t in d["turns"]]
    instrumented = all(t.get("composition") for t in turns)
    reasons = Counter(
        t["composition"]["fallback_reason"]
        for t in turns
        if t.get("composition", {}).get("fallback_reason")
    )
    repeated = 0
    for dialogue in dialogues:
        seen = set()
        for turn in dialogue["turns"]:
            text = turn["assistant"]["text"]
            repeated += text in seen
            seen.add(text)
    drafted = sum(t.get("composition", {}).get("origin") == "llm" for t in turns)
    return {
        "dialogues": len(dialogues),
        "turns": len(turns),
        "instrumentation_available": instrumented,
        "llm_drafted_turns": drafted if instrumented else None,
        "llm_drafted_ratio": drafted / len(turns) if instrumented else None,
        "fallback_reasons": dict(reasons) if instrumented else None,
        "exact_repeated_responses": repeated,
        "turns_with_multiple_questions": sum(t["assistant"]["text"].count("?") > 1 for t in turns),
        "policy_violations": sum(
            not CommercialPolicyEngine().validate_output(t["assistant"]["text"]) for t in turns
        ),
        "social_turns_with_technical_queries": sum(
            is_reference_social(t["user"]) and "get_vehicle_details" in t["tools"]
            for t in turns
        ),
    }


class QualityModel:
    """Synthetic protocol partner, using only supplied data, no provider access."""

    async def complete(self, messages, tools):
        if tools:
            return ModelReply(tool_calls=[ToolCall(name="list_vehicles")])
        content = messages[-1]["content"]
        if content.startswith("{"):
            context = json.loads(content)
            if context.get("task") == "interpret_intent":
                return ModelReply(
                    text=json.dumps({"kind": "other", "evidence_quote": context["message"][:200]})
                )
            if context.get("task") == "compose_conversation":
                intent = context["intent"]
                text = {
                    "welcome": "Opa! Seja bem-vindo.",
                    "brand": "Posso te apresentar o B10 e o C10 a partir dos modelos e fotos da nossa base.",
                    "other": "Estou acompanhando o que você está contando. Pode seguir no seu ritmo.",
                    "positive": "Pelo que você contou, o visual chamou sua atenção. Podemos olhar a escolha a partir da sua rotina.",
                    "negative": "Entendi sua impressão. Podemos seguir pelo que você procura, sem insistir nesse ponto.",
                    "doubt": "Vamos por partes, no seu ritmo. Pode me contar o que ficou em aberto.",
                    "more": "Podemos continuar pelo que faz diferença na sua escolha.",
                    "first_electric": "Vamos explorar suas dúvidas aos poucos, sem pressupor experiência anterior com elétricos.",
                    "objection": "Entendi sua preocupação. Vamos olhar esse ponto com calma a partir da sua rotina.",
                    "distance_context": "Vou considerar a distância que você descreveu ao longo da conversa.",
                    "short": "Certo, seguimos a partir do que você já me contou.",
                    "usage": "Entendi o papel do carro na sua rotina. Vamos considerar o que você precisa nesse uso.",
                    "charging_context": "Você mencionou recarga em casa. Vou considerar isso ao longo da conversa.",
                    "missing_evidence": "Esse ponto ainda está em aberto na base aprovada. Podemos continuar pelo que você precisa na sua rotina.",
                }.get(intent, "Vamos continuar a partir do seu interesse e das suas prioridades.")
                if intent == "usage" and context["profile"].get("usage") == "aplicativos":
                    text = "Entendi que você pensa no carro para trabalhar com aplicativo. Vamos olhar sua rotina antes de tirar conclusões."
                if intent == "usage" and "espaco" in context["profile"].get("needs", []):
                    text = "Você está pensando na sua rotina com a família. Vamos considerar o que vocês precisam levar."
                question = context.get("suggested_question")
                if (
                    intent == "welcome"
                    and not context.get("name_known")
                    and not context.get("introduced")
                ):
                    question = {"key": "preferred_name", "text": "Como você prefere ser chamado?"}
                return ModelReply(
                    text=json.dumps(
                        {
                            "text": text,
                            "fact_ids": [f["id"] for f in context["facts"]],
                            "question": question,
                        },
                        ensure_ascii=False,
                    ),
                    input_tokens=100,
                    output_tokens=40,
                )
            if "reaction" in context:
                return ModelReply(
                    text=json.dumps(
                        {
                            "acknowledgement": "Podemos explorar o que chamou sua atenção.",
                            "question": None,
                        }
                    )
                )
            if "variants" in context:
                return ModelReply(text='{"variant":1}')
        evidence = json.loads(content.split(": ", 1)[1])
        return ModelReply(
            text=json.dumps({"fact_ids": [f["id"] for f in evidence.get("facts", [])]})
        )


async def evaluate(revision=None):
    scenarios = json.loads(Path("tests/fixtures/conversations/lia-quality.json").read_text())
    rows = []
    for scenario in scenarios:
        agent = build_agent(reviewed_catalog=True, test_media=True)
        agent.llm = QualityModel()
        turns = []
        for message in scenario["messages"]:
            kind = message.get("type", "text") if isinstance(message, dict) else "text"
            text = message["transcript"] if isinstance(message, dict) else message
            options = (
                {"input_type": kind}
                if "input_type" in inspect.signature(agent.turn).parameters
                else {}
            )
            answer = await agent.turn(scenario["id"], text, **options)
            state = agent.sessions[("local", scenario["id"])]
            composition = state.get("composition", {})
            turns.append(
                {
                    "user": text,
                    "input_type": kind,
                    "assistant": answer.model_dump(mode="json"),
                    "tools": [e["name"] for e in state.get("tool_events", [])],
                    "composition": composition,
                    "usage": state["usage"],
                    "vehicle_id": state["lead_profile"]["vehicle_id"],
                }
            )
        rows.append({"id": scenario["id"], "turns": turns})
    return {
        "commit": revision
        or (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "implementation": "baseline-archive" if revision else "working-tree-refactor",
        "audio_evaluation": "synthetic transcripts only; no STT or WhatsApp requests",
        "source_sha256": {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in ("app/agent/service.py", "app/agent/social.py", "app/agent/composition.py")
            if Path(path).exists()
        },
        "dataset_sha256": hashlib.sha256(
            Path("tests/fixtures/conversations/lia-quality.json").read_bytes()
        ).hexdigest(),
        "synthetic": True,
        "real_llm_calls": 0,
        "dialogues": rows,
        "metrics": summarize(rows),
        "not_measured": ["real_model_naturalness", "human_ratings", "real_latency", "real_cost"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", default=None)
    args = parser.parse_args()
    payload = asyncio.run(evaluate(args.revision))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["metrics"], ensure_ascii=False))
