"""ner client: the stub replays recorded spans filtered to the asked labels; the wire format."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from nip.runtime.clients import ner
from nip.runtime.clients.ner import Actor, Entity, ServeNER, StubNER

ADDR = Entity(text="12 rue de Rivoli", label="address", start=0, end=16, score=0.7)
ORG = Entity(text="Siemens AG", label="organization", start=20, end=30, score=0.9)


def test_stub_replays_and_filters_by_label() -> None:
    stub = StubNER({"t": [ADDR, ORG]})
    assert stub.predict("t", ["address", "organization"]) == [ADDR, ORG]
    assert stub.predict("t", ["organization"]) == [ORG]
    assert stub.predict("other", ["address"]) == []


def test_serve_client_posts_text_and_labels() -> None:
    seen: dict[str, Any] = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            out = json.dumps({"variant": "v", "entities": [ADDR.model_dump()]}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a: object) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        client = ServeNER("gliner-x-base", f"http://127.0.0.1:{srv.server_port}")
        assert client.predict("12 rue de Rivoli", ["address"]) == [ADDR]
    finally:
        srv.shutdown()
    assert seen == {
        "path": "/models/gliner-x-base",
        "body": {"text": "12 rue de Rivoli", "labels": ["address"]},
    }


def test_actor_answers_serve_requests_with_the_backends_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Req:
        async def json(self) -> dict[str, Any]:
            return {"text": "t", "labels": ["address"]}

    class Backend:
        def __init__(self, variant: str) -> None:
            pass

        def predict(self, text: str, labels: list[str]) -> list[Entity]:
            assert (text, labels) == ("t", ["address"])
            return [ADDR]

    monkeypatch.setattr(ner, "GlinerBackend", Backend)
    assert asyncio.run(Actor("gliner-x-base")(Req())) == {
        "variant": "gliner-x-base",
        "entities": [ADDR.model_dump()],
    }
