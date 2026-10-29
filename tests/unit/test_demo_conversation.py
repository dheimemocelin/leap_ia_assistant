import json

import pytest

from app.agent.llm import ModelReply
from app.api.chat import build_agent


class EvidenceOnlyLLM:
    async def complete(self, messages, tools):
        assert not tools
        evidence = json.loads(messages[-1]["content"].split(": ", 1)[1])
        if evidence.get("kind") == "get_vehicle_details":
            assert any(
                term in messages[-2]["content"] for term in ["conhecer", "autonomia", "potência"]
            )
            return ModelReply(text=json.dumps({"fact_ids": [f["id"] for f in evidence["facts"]]}))
        return ModelReply(text="Separei as fotos autorizadas deste veículo.")


@pytest.fixture
def demo():
    agent = build_agent(reviewed_catalog=True, test_media=True)
    agent.llm = EvidenceOnlyLLM()
    return agent


async def test_asking_powertrain_keeps_original_characteristics_request(demo):
    first = await demo.turn("one", "Quero conhecer o B10")
    assert "BEV" in first.text
    answer = await demo.turn("one", "bev")
    assert "218" in answer.text and "405" in answer.text
    photos = await demo.turn("one", "Me mostra por dentro")
    assert len(photos.media_ids) == 2
    assert all("b10-bev" in m for m in photos.media_ids)


@pytest.mark.parametrize("vehicle", ["B10 BEV", "B10 REEV", "C10 BEV"])
async def test_actual_authorized_demo_photos_are_available(demo, vehicle):
    reply = await demo.turn(vehicle, "Me manda fotos do " + vehicle)
    assert len(reply.media_ids) == 3
    assert not reply.handoff_required


async def test_specific_missing_battery_not_replaced_with_unrelated_summary(demo):
    reply = await demo.turn("missing", "Qual a capacidade da bateria do B10 BEV?")
    assert reply.handoff_required and not reply.source_ids
    assert "405" not in reply.text and "218" not in reply.text


async def test_photos_are_rendered_without_model_generated_urls(demo):
    class NeverCall:
        async def complete(self, *args):
            raise AssertionError("Image replies must not need an LLM")

    demo.llm = NeverCall()
    response = await demo.turn("photo-no-model", "Fotos do B10 BEV")
    assert len(response.media_ids) == 3
    assert "http" not in response.text
    assert demo.sessions[("local", "photo-no-model")]["usage"]["calls"] == 0


async def test_greeting_is_natural_without_model(demo):
    response = await demo.turn("greeting", "Oi!")
    assert "B10" in response.text and "C10" in response.text
    assert demo.sessions[("local", "greeting")]["usage"]["calls"] == 0


async def test_technical_question_after_photos_does_not_repeat_photos(demo):
    await demo.turn("switch", "Fotos do B10 BEV")
    answer = await demo.turn("switch", "Qual a potência do B10 BEV?")
    assert "218" in answer.text and not answer.media_ids


async def test_feminine_powertrain_answer_keeps_photo_intent(demo):
    await demo.turn("feminine", "Quero fotos do B10")
    photos = await demo.turn("feminine", "a elétrica")
    assert len(photos.media_ids) == 3


async def test_photo_caption_is_natural_and_names_selected_vehicle(demo):
    response = await demo.turn("caption", "Fotos do B10 REEV")
    assert "B10 REEV" in response.text
    assert "foto(s)" not in response.text
    assert "ampliar" in response.text
    assert demo.sessions[("local", "caption")]["usage"]["calls"] == 0


async def test_yes_to_photo_offer_keeps_the_vehicle(demo):
    facts = await demo.turn("offer", "Quero conhecer o B10 BEV")
    assert "Quer ver algumas fotos" in facts.text
    photos = await demo.turn("offer", "sim")
    assert len(photos.media_ids) == 3
    assert all("b10-bev" in m for m in photos.media_ids)
