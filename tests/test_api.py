"""API tests. The Anthropic client is replaced with a fake so tests run
offline and free; the fake returns canned JSON the way the real model would."""

import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_llm_client

VALID_MODEL_JSON = {
    "title": "200A Load Center, 40-Space",
    "category": "electrical",
    "brand": "Square D",
    "model_number": "QO140M200PC",
    "specs": {"amperage": "200 A", "spaces": "40"},
    "condition_tier": "new_surplus",
    "condition_notes": "Boxed, factory sealed.",
    "quantity_estimate": None,
    "confidence": 0.9,
}


class FakeClient:
    def __init__(self, payload: str):
        self._payload = payload
        self.messages = SimpleNamespace(create=self._create)
        self.last_kwargs = None

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        block = SimpleNamespace(type="text", text=self._payload)
        return SimpleNamespace(content=[block])


@pytest.fixture
def client_with_fake():
    fake = FakeClient(json.dumps(VALID_MODEL_JSON))
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def test_healthz():
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_draft_listing_sku_only(client_with_fake):
    client, _ = client_with_fake
    resp = client.post("/v1/listings/draft", data={"sku": "QO140M200PC"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["listing"]["category"] == "electrical"
    # Electrical -> high risk from the deterministic engine
    assert body["verification"]["risk_tier"] == "high"
    assert body["verification"]["physical_inspection_required"] is True


def test_draft_listing_with_image(client_with_fake):
    client, fake = client_with_fake
    resp = client.post(
        "/v1/listings/draft",
        data={"sku": "QO140M200PC", "notes": "pallet of 12"},
        files={"image": ("panel.jpg", io.BytesIO(b"\xff\xd8fakejpeg"), "image/jpeg")},
    )
    assert resp.status_code == 200
    # The fake received an image block + text block
    content = fake.last_kwargs["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert "pallet of 12" in content[1]["text"]


def test_rejects_bad_image_type(client_with_fake):
    client, _ = client_with_fake
    resp = client.post(
        "/v1/listings/draft",
        data={"sku": "ABC"},
        files={"image": ("f.txt", io.BytesIO(b"hi"), "text/plain")},
    )
    assert resp.status_code == 415


def test_model_garbage_returns_502():
    fake = FakeClient("I'm sorry, I can't produce JSON today.")
    app.dependency_overrides[get_llm_client] = lambda: fake
    try:
        resp = TestClient(app).post("/v1/listings/draft", data={"sku": "ABC"})
        assert resp.status_code == 502
    finally:
        app.dependency_overrides.clear()


def test_model_fenced_json_is_tolerated():
    fenced = "```json\n" + json.dumps(VALID_MODEL_JSON) + "\n```"
    fake = FakeClient(fenced)
    app.dependency_overrides[get_llm_client] = lambda: fake
    try:
        resp = TestClient(app).post("/v1/listings/draft", data={"sku": "ABC"})
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
