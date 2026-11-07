"""text_llm / vlm / judge_llm: vLLM's OpenAI-compatible API behind `/models/<variant>`.

Every call is structured (D-025, tech-stack.md Build notes): instructor in JSON-schema mode, so
`response_format` carries the JSON schema of a Pydantic model; temperature 0; Qwen thinking off
(`chat_template_kwargs.enable_thinking: false`); `max_retries=1` = exactly one repair call when the
reply fails the schema or a validator, which gets `context` as its validation context.
"""

import base64
import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from nip.runtime.clients.stub import REPLAY_VARIANT, record, record_key, recorded, stub_instance

log = logging.getLogger(__name__)

# Serve's HTTP proxy runs on every Ray node; host-side dev reaches it through compose.dev.yaml
# (NIP_SERVE_URL=http://127.0.0.1:8001, R9).
SERVE_URL = os.environ.get("NIP_SERVE_URL", "http://127.0.0.1:8000")


def _image_part(data: bytes) -> dict[str, Any]:
    magic = {b"\x89PNG": "image/png", b"GIF8": "image/gif", b"RIFF": "image/webp"}
    mime = magic.get(data[:4], "image/jpeg")
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
        import instructor
        from openai import OpenAI

        self.variant = variant
        # max_retries=0: the SDK's default 2 retries re-sent a timed-out reply at T=0, so a looping
        # scene held its slot for 3 x timeout_s (2.1B: 1,802 s); instructor's one repair stays.
        self._client = OpenAI(
            base_url=f"{base_url}/models/{variant}/v1",
            api_key="unused",
            timeout=timeout_s,
            max_retries=0,
        )
        self._structured = instructor.from_openai(self._client, mode=instructor.Mode.JSON_SCHEMA)

    def complete[M: BaseModel](
        self,
        prompt: str,
        schema: type[M],
        *,
        images: Sequence[bytes] = (),
        system: str | None = None,
        max_tokens: int = 1024,
        context: dict[str, Any] | None = None,
    ) -> M:
        _, raw = self._structured.chat.completions.create_with_completion(
            model=self.variant,
            messages=messages(prompt, images, system),
            response_model=schema,
            max_retries=1,
            context=context,
            temperature=0,
            max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        reply = raw.choices[0].message.content or ""  # the reply that validated (after a repair)
        if rec := os.environ.get("NIP_LLM_RECORD_DIR"):  # D-020: recordings for the cpu profile
            key = record_key(self.variant, prompt, schema, system)
            record(key, self.variant, schema.__name__, reply, Path(rec))
        # a plain instance: instructor's carries its response object in __dict__
        return schema.model_validate_json(reply, context=context)


class StubLLM:
    """Same interface, no model (NIP_PROFILE=cpu): the recorded REPLAY_VARIANT response for this
    exact call when there is one, else the deterministic minimal instance of the schema."""

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
        context: dict[str, Any] | None = None,
    ) -> M:
        key = record_key(REPLAY_VARIANT, prompt, schema, system)
        reply = recorded(key)
        if reply is None:  # prompt, registry or schema drift shows up here (review M-9)
            log.info("no recorded %s reply %s: minimal stub instance", schema.__name__, key[:12])
            return stub_instance(schema)
        return schema.model_validate_json(reply, context=context)
