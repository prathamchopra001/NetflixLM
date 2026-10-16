"""text_llm / vlm / judge_llm: vLLM's OpenAI-compatible API behind `/models/<variant>`.

Every call is structured: `response_format` carries the JSON schema of a Pydantic model
(hardware-adaptation.md › Serving), temperature 0.
"""

import base64
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from nip.runtime.clients.stub import stub_instance

SERVE_URL = "http://127.0.0.1:8000"  # Serve's HTTP proxy runs on every Ray node


def _image_part(data: bytes) -> dict[str, Any]:
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return {"type": "image_url", "image_url": {"url": url}}


def messages(prompt: str, images: Sequence[bytes] = (), system: str | None = None) -> list[Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content += [_image_part(i) for i in images]
    return ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": content}
    ]


class LLMClient:
    def __init__(self, variant: str, base_url: str = SERVE_URL, timeout_s: float = 600) -> None:
        from openai import OpenAI

        self.variant = variant
        self._client = OpenAI(
            base_url=f"{base_url}/models/{variant}/v1", api_key="unused", timeout=timeout_s
        )

    def complete[M: BaseModel](
        self,
        prompt: str,
        schema: type[M],
        *,
        images: Sequence[bytes] = (),
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> M:
        r = self._client.chat.completions.create(
            model=self.variant,
            messages=messages(prompt, images, system),
            temperature=0,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
        )
        return schema.model_validate_json(r.choices[0].message.content or "")


class StubLLM:
    """Same interface; deterministic schema-valid output, no model (NIP_PROFILE=cpu)."""

    def __init__(self, variant: str = "stub") -> None:
        self.variant = variant

    def complete[M: BaseModel](
        self,
        prompt: str,
        schema: type[M],
        *,
        images: Sequence[bytes] = (),
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> M:
        return stub_instance(schema)
