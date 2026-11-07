"""Capability clients: deterministic schema-valid stubs; the LLM client's wire format."""

import json
import threading
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from nip.contracts import Autoscaling, Gpu, HardwareInventory, Node, Slot
from nip.runtime.catalog import load_catalog
from nip.runtime.clients import LLMClient, StubLLM, llm
from nip.runtime.clients.stub import stub_instance
from nip.runtime.planner import plan

CATALOG = load_catalog(Path(__file__).parents[3] / "config" / "catalog.yaml")
LAPTOP = HardwareInventory(
    fingerprint="sim",
    nodes=[
        Node(
            node_id="n0",
            cpus=16,
            ram_gb=31.0,
            gpus=[
                Gpu(
                    index=0,
                    name="g",
                    vram_total_gb=8.0,
                    vram_free_gb=7.15,
                    compute_capability="8.9",
                )
            ],
        )
    ],
    autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0),
)


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"


class Span(BaseModel):
    text: str = Field(min_length=6)
    frames: tuple[int, int]
    score: float = Field(ge=0.25, le=1)


class Answer(BaseModel):
    color: Color
    count: int = Field(gt=2)
    spans: list[Span] = Field(min_length=2)
    note: str | None
    tags: list[str] = []


def test_stub_instance_is_valid_and_deterministic() -> None:
    a = stub_instance(Answer)
    assert a == stub_instance(Answer)
    assert a.color is Color.RED and a.count == 3 and len(a.spans) == 2
    assert a.spans[0].score == 0.25 and len(a.spans[0].text) >= 6 and a.note == "stub"


def test_stub_llm_returns_schema_valid_output() -> None:
    assert StubLLM().complete("Is it red?", Answer) == stub_instance(Answer)


def test_llm_factory_follows_the_plan() -> None:
    stub = plan(LAPTOP, CATALOG, {s: 10 for s in Slot}, stub=True)
    assert isinstance(llm(stub, CATALOG, Slot.TEXT_LLM), StubLLM)
    real = plan(LAPTOP, CATALOG, {s: 10 for s in Slot})
    c = llm(real, CATALOG, Slot.VLM, base_url="http://h:1")
    assert isinstance(c, LLMClient) and c.variant == "qwen3.5-4b-awq"
    assert str(c._client.base_url) == "http://h:1/models/qwen3.5-4b-awq/v1/"


def test_llm_client_sends_schema_and_images_and_parses_reply() -> None:
    seen: dict[str, Any] = {}
    reply = Answer(color=Color.BLUE, count=5, spans=[stub_instance(Span)] * 2, note="x")

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            msg = {"role": "assistant", "content": reply.model_dump_json()}
            body = json.dumps(
                {
                    "id": "1",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "m",
                    "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
                }
            ).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a: Any) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LLMClient("m", f"http://127.0.0.1:{srv.server_port}")
        got = c.complete("Which?", Answer, images=[b"\x89PNG...."], system="be brief")
    finally:
        srv.shutdown()
    assert got == reply
    assert seen["path"] == "/models/m/v1/chat/completions"
    b = seen["body"]
    assert b["model"] == "m" and b["temperature"] == 0
    assert b["response_format"]["json_schema"]["schema"] == Answer.model_json_schema()
    assert b["messages"][0] == {"role": "system", "content": "be brief"}
    parts = b["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "Which?"}
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
