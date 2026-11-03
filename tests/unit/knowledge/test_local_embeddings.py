from pathlib import Path

import pytest


def test_local_real_e5_runs_without_network_and_preserves_dimension():
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    from app.knowledge.embeddings import LocalE5

    model_dir = Path(".local/knowledge-models/e5-small")
    if not model_dir.exists():
        pytest.skip("Optional model artifact not installed; never download in tests")
    model = LocalE5(model_dir)
    vectors = model.encode(
        [
            "O carregamento programado permite escolher o horário.",
            "A saída de ar pode ser direcionada para cima e para baixo.",
        ]
    )
    query = model.encode(["Dá pra agendar a hora de carregar?"], query=True)[0]
    assert len(query) == 384 and all(len(v) == 384 for v in vectors)
    score = [sum(a * b for a, b in zip(v, query, strict=True)) for v in vectors]
    assert score[0] > score[1]
    with pytest.raises(ValueError, match="token limit"):
        model.encode(["carregamento " * 1000])
