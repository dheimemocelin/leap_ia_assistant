import json
from datetime import UTC, datetime

import pytest

from app.knowledge.retrieval import KnowledgeIndex, KnowledgeQuery
from app.knowledge.review import ReviewEvent, event_hash, make_segment


class SyntheticEmbeddings:
    model_id = "synthetic-not-semantic-v1"

    def __init__(self):
        self.calls = 0

    def encode(self, texts, query=False):
        self.calls += 1
        return [[1.0, 0.0] if "carg" in t else [0.0, 1.0] for t in texts]


@pytest.fixture
def indexed(tmp_path):
    s = make_segment(
        "a" * 64,
        19,
        19,
        "Recarga programada",
        "O carregamento programado é usado com carregador CA.",
        "rec-1",
    )
    e = ReviewEvent(
        segment_id=s.segment_id,
        text_sha256=s.text_sha256,
        source_recovery_key="rec-1",
        status="approved",
        reviewer="synthetic",
        reviewed_at=datetime.now(UTC),
        reason="Synthetic review",
        visual_comparison=True,
    )
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        json.dumps({"segments": [s.model_dump()], "events": [e.model_dump(mode="json")]})
    )
    embed = SyntheticEmbeddings()
    index = KnowledgeIndex(tmp_path / "knowledge.sqlite3", bundle, embed)
    identity = {
        "a" * 64: {
            "model": "B10",
            "powertrain": "BEV",
            "model_year": 2027,
            "market": "BR",
            "identity_verified": True,
        }
    }
    assert index.build(identity) == 1
    return index, embed, bundle, s, e, identity


def test_real_lexical_and_fusion_code_with_simulated_embedding(indexed):
    index, _, _, s, _, _ = indexed
    for mode in ["lexical", "vector", "hybrid"]:
        result = index.search_preview(
            "carregamento programado", document_sha256="a" * 64, mode=mode
        )
        assert result[0]["evidence_id"] == s.segment_id and result[0]["page_start"] == 19
        assert result[0]["requires_answer_grounding"]


def test_passage_embedding_cache_reuses_same_version(indexed):
    index, embed, _, _, _, identity = indexed
    calls = embed.calls
    index.build(identity)
    assert embed.calls == calls
    embed.model_id = "synthetic-v2"
    index.build(identity)
    assert embed.calls == calls + 1


@pytest.mark.parametrize(
    "model,powertrain,year",
    [("B10", "REEV", 2027), ("C10", "BEV", 2027), ("B10", "BEV", 2026), ("B10", "BEV", None)],
)
def test_strict_customer_filters_fail_closed(indexed, model, powertrain, year):
    index, *_ = indexed
    result = index.search_knowledge(
        KnowledgeQuery(
            question="Como carrega?", model=model, powertrain=powertrain, model_year=year
        )
    )
    assert not result["evidence"]


def test_approved_matching_configuration_returns_citations(indexed):
    index, *_ = indexed
    result = index.search_knowledge(
        KnowledgeQuery(question="carregamento", model="B10", powertrain="BEV", model_year=2027)
    )
    assert result["status"] == "evidence_found"
    assert result["evidence"][0]["page_start"] == 19


def test_unverified_identity_cannot_be_published(indexed):
    index, _, _, _, _, identity = indexed
    identity["a" * 64]["identity_verified"] = False
    index.build(identity)
    assert not index.search_knowledge(
        KnowledgeQuery(question="carregamento", model="B10", powertrain="BEV", model_year=2027)
    )["evidence"]


def test_revocation_removes_results_without_rebuilding(indexed):
    index, _, bundle, s, e, _ = indexed
    revoked = e.model_copy(update={"status": "rejected", "previous_event_sha256": event_hash(e)})
    bundle.write_text(
        json.dumps(
            {
                "segments": [s.model_dump()],
                "events": [x.model_dump(mode="json") for x in [e, revoked]],
            }
        )
    )
    assert index.search_preview("carregamento", document_sha256="a" * 64) == []


@pytest.mark.parametrize(
    "question",
    [
        "Qual o preço?",
        "Dá desconto?",
        "Como desmontar a bateria de alta tensão?",
        "Como desativar o airbag?",
    ],
)
def test_financial_and_hazardous_requests_do_not_retrieve(indexed, question):
    index, embed, *_ = indexed
    calls = embed.calls
    assert not index.search_preview(question, document_sha256="a" * 64)
    assert calls == embed.calls


def test_other_document_cannot_leak_evidence(indexed):
    index, *_ = indexed
    assert not index.search_preview("carregamento", document_sha256="b" * 64)


def test_fts_query_injection_is_data_only(indexed):
    index, *_ = indexed
    assert isinstance(
        index.search_preview('" OR * DROP TABLE chunks; --', document_sha256="a" * 64), list
    )
    assert index.search_preview("carregamento", document_sha256="a" * 64)
