"""Local retrieval evaluation only; no LLM, WhatsApp or CRM calls."""

import argparse
import json
import time
from pathlib import Path

from app.knowledge.embeddings import LocalE5
from app.knowledge.retrieval import KnowledgeIndex, KnowledgeQuery

QUESTIONS = {
    "charging": [
        "Dá pra programar o horário de carregar?",
        "Onde ativo o agendamento da carga?",
        "Agendar a carga funciona com carregador CA?",
        "O carregamento programado também vale pra carga rápida?",
        "Posso configurar limite de carregamento?",
        "Como escolho o tempo do carregamento?",
    ],
    "battery": [
        "De onde vem a energia do carro?",
        "A bateria pode carregar e descarregar várias vezes?",
        "O carro recupera energia ao frear?",
        "A bateria carrega quando desacelero?",
        "A bateria fica debaixo do carro?",
        "Preciso tomar cuidado com a bateria em piso irregular?",
    ],
    "multimedia": [
        "O que aparece na tela principal?",
        "Consigo personalizar a barra inferior da tela?",
        "Tem indicação de Bluetooth na tela?",
        "Posso mexer na tela enquanto dirijo?",
        "Onde ficam os controles do ar na tela?",
        "Quais são os atalhos da central multimídia?",
    ],
    "comfort": [
        "Como ajusto a direção do ar no painel?",
        "Dá para fechar as saídas de ar centrais?",
        "Como movo a ventilação central para cima e para baixo?",
        "Como ajusto o fluxo de ar na saída central frontal?",
        "Como direcionar o vento das saídas frontais?",
        "Quero diminuir a passagem de ar pelo difusor central",
    ],
    "safety": [
        "Passageiro atrás também precisa de cinto?",
        "Criança precisa de cadeirinha?",
        "Mesmo numa velocidade baixa tem que usar cinto?",
        "Posso colocar enfeites no cinto de segurança?",
        "Posso deixar criança brincar com o cinto?",
        "Posso inclinar muito o encosto ao usar o cinto?",
    ],
}


def evaluate(index, bundle_path):
    bundle = json.loads(Path(bundle_path).read_text())
    source = {s["topic"]: s for s in bundle["sources"]}
    rows = []
    for topic, questions in QUESTIONS.items():
        for q in questions:
            for mode in ["lexical", "vector", "hybrid"]:
                start = time.perf_counter()
                hits = index.search_preview(
                    q, document_sha256=source[topic]["document_sha256"], limit=3, mode=mode
                )
                ids = [h["evidence_id"] for h in hits]
                expected = source[topic]["segment_id"]
                rank = ids.index(expected) + 1 if expected in ids else None
                rows.append(
                    {
                        "question": q,
                        "topic": topic,
                        "mode": mode,
                        "expected_evidence": expected,
                        "returned_evidence": ids,
                        "rank": rank,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    }
                )
    summary = {}
    for mode in ["lexical", "vector", "hybrid"]:
        sample = [r for r in rows if r["mode"] == mode]
        summary[mode] = {
            "queries": len(sample),
            "recall_at_3": sum(r["rank"] is not None for r in sample) / len(sample),
            "mrr_at_3": sum(1 / r["rank"] if r["rank"] else 0 for r in sample) / len(sample),
            "top1": sum(r["rank"] == 1 for r in sample) / len(sample),
            "mean_latency_ms": sum(r["latency_ms"] for r in sample) / len(sample),
        }
    negatives = []
    for q in [
        "Qual o preço?",
        "Como desmontar a bateria de alta tensão?",
        "Como desativar o airbag?",
    ]:
        negatives.append(
            {
                "question": q,
                "evidence_count": len(
                    index.search_preview(q, document_sha256=source["charging"]["document_sha256"])
                ),
            }
        )
    strict = index.search_knowledge(
        KnowledgeQuery(
            question="Como funciona o carregamento programado?",
            model="B10",
            powertrain="BEV",
            model_year=2027,
        )
    )
    return {
        "scope": "document_preview_only",
        "model": index.embedder.model_id,
        "independent_human_gold": False,
        "gold_basis": "engineer-authored questions mapped to visually reviewed bounded sections",
        "summary": summary,
        "queries": rows,
        "blocked_requests": negatives,
        "strict_customer_tool_status": strict["status"],
        "llm_calls": 0,
        "paid_api_calls": 0,
        "naturalness_evaluation": "not_run",
        "response_generation": "not_implemented",
        "open_domain_abstention_evaluation": "pending",
        "unknown_year_not_assumed": True,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    bundle = "docs/knowledge/a1-reviewed-segments.json"
    index = KnowledgeIndex(
        ".local/knowledge-rag/preview.sqlite3", bundle, LocalE5(".local/knowledge-models/e5-small")
    )
    index.build()
    report = evaluate(index, bundle)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
