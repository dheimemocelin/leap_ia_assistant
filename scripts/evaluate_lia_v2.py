"""Generate synthetic before/after transcripts. No real LLM or channel calls."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from app.api.chat import build_agent
from app.config import settings
from app.pilot_store import PilotStore
from tests.unit.test_sales_delivery import SalesModel

SCENARIOS = {
    "name_close_return": [
        "Oi",
        "Pessoa Sintetica",
        "B10 BEV",
        "Vou pensar",
        "Oi",
        "Me fala daquele carro",
    ],
    "repeat_and_other_photo": ["C10 BEV", "Manda novamente", "Cadê?", "Tem outra foto?"],
    "technical_day_return": [
        "C10 BEV",
        "Pessoa Sintetica",
        "Qual a autonomia?",
        "Até mais",
        "Qual a autonomia dele?",
    ],
    "usage_and_visit_decline": [
        "B10 BEV",
        "Pessoa Sintetica",
        "Vou usar para Uber",
        "Quero visitar a loja",
        "Não quero falar com vendedor",
        "Quero continuar",
    ],
    "authorized_local_queue": [
        "Oi",
        "Pessoa Sintetica",
        "B10 BEV",
        "Quero falar com um consultor",
        "sim",
        "Qual a autonomia?",
    ],
    "financial_and_pause": [
        "B10 BEV",
        "Pessoa Sintetica",
        "Qual o preço?",
        "Não",
        "Depois eu vejo",
        "Oi",
    ],
    "model_change_and_rear": [
        "B10 BEV",
        "Pessoa Sintetica",
        "C10 BEV",
        "Quero ver a traseira",
        "Mostra de novo",
        "Não tenho interesse",
    ],
}


async def evaluate():
    # Explicitly disable provider and knowledge initialization before creating the simulator.
    settings.llm_provider = "disabled"
    settings.lia_knowledge_enabled = False
    report = {
        "evidence_type": "synthetic_graph_execution",
        "paid_calls": 0,
        "human_quality_review": "pending",
        "external_delivery": "not_executed",
        "scenarios": [],
    }
    with tempfile.TemporaryDirectory(prefix="lia-v2-evaluation-") as tmp:
        for name, messages in SCENARIOS.items():
            scenario = {"name": name}
            for enabled, label in [(False, "before"), (True, "after")]:
                store = PilotStore(str(Path(tmp) / f"{name}-{label}.db"))
                thread = store.open_thread("synthetic-person", "whatsapp:synthetic")
                agent = build_agent(
                    reviewed_catalog=True, test_media=True, orchestration_enabled=True
                )
                agent.sales_focus = True
                agent.conversation_v2_enabled = enabled
                agent.handoff_mode = "local"
                agent.memory_store = store
                agent.llm = SalesModel()
                turns = []
                for message in messages:
                    answer = await agent.turn(
                        thread["conversation_id"],
                        message,
                        owner=thread["owner"],
                        trusted_contact_phone="5511999990000",
                    )
                    state = agent.sessions[(thread["owner"], thread["conversation_id"])]
                    turns.append(
                        {
                            "user": message,
                            "assistant": answer.text,
                            "source_ids": answer.source_ids,
                            "media_ids": answer.media_ids,
                            "tools": [e["name"] for e in state["tool_events"]],
                            "session_status": (state.get("conversation_session") or {}).get(
                                "status"
                            ),
                            "commercial_state": state.get("commercial_state"),
                            "composition_origin": state.get("composition", {}).get("origin"),
                            "fallback_reason": state.get("composition", {}).get("fallback_reason"),
                            "questions": answer.text.count("?"),
                        }
                    )
                scenario[label] = {
                    "turns": turns,
                    "handoffs": store.handoff_metrics(),
                    "conversion": store.conversion_metrics(),
                    "metrics": {
                        "turns": len(turns),
                        "llm_authored_turns": sum(t["composition_origin"] == "llm" for t in turns),
                        "fallback_turns": sum(bool(t["fallback_reason"]) for t in turns),
                        "responses_with_multiple_questions": sum(t["questions"] > 1 for t in turns),
                    },
                }
            report["scenarios"].append(scenario)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/lia-v2/transcripts.json"))
    args = parser.parse_args()
    report = asyncio.run(evaluate())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"scenarios": len(report["scenarios"]), "output": str(args.output), "paid_calls": 0}
        )
    )


if __name__ == "__main__":
    main()
