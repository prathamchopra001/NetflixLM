"""ocr client: the stub replays recorded lines; Serve's wire format round-trips."""

import asyncio
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from nip.runtime.clients import ocr
from nip.runtime.clients.ocr import Actor, OcrLine, ServeOCR, StubOCR, fingerprint

LINE = OcrLine(text="CALL 555-0142", box=(0.1, 0.2, 0.3, 0.05), confidence=0.98)


def test_stub_replays_by_image_bytes_and_reads_nothing_otherwise(tmp_path: Path) -> None:
    img = tmp_path / "0_0.jpg"
    img.write_bytes(b"frame-a")
    stub = StubOCR({fingerprint(b"frame-a"): [LINE]})
    assert stub.read(img) == [LINE] == stub.read(b"frame-a")
    assert stub.read(b"frame-b") == []
    assert StubOCR().read(img) == []


def test_ocr_line_rejects_confidence_outside_0_1() -> None:
    with pytest.raises(ValueError):
        OcrLine(text="x", box=(0, 0, 1, 1), confidence=1.5)


def test_serve_client_posts_image_bytes_and_parses_lines() -> None:
    seen: dict[str, Any] = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen["path"] = self.path
            seen["body"] = self.rfile.read(int(self.headers["content-length"]))
            out = json.dumps({"variant": "v", "lines": [LINE.model_dump()]}).encode()
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
        client = ServeOCR("pp-ocrv6-medium", f"http://127.0.0.1:{srv.server_port}")
        assert client.read(b"jpeg-bytes") == [LINE]
    finally:
        srv.shutdown()
    assert seen == {"path": "/models/pp-ocrv6-medium", "body": b"jpeg-bytes"}


def test_actor_answers_serve_requests_with_the_backends_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Req:
        async def body(self) -> bytes:
            return b"frame"

    class Backend:
        def read(self, image: bytes) -> list[OcrLine]:
            assert image == b"frame"
            return [LINE]

    monkeypatch.setattr(ocr, "RapidOcrBackend", Backend)
    assert asyncio.run(Actor("pp-ocrv6-medium")(Req())) == {
        "variant": "pp-ocrv6-medium",
        "lines": [LINE.model_dump()],
    }


def test_serve_url_follows_nip_serve_url() -> None:
    code = "from nip.runtime.clients.ocr import ServeOCR; print(ServeOCR()._url)"
    env = {**os.environ, "NIP_SERVE_URL": "http://127.0.0.1:8001"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert out.stdout.strip() == "http://127.0.0.1:8001/models/pp-ocrv6-medium"
