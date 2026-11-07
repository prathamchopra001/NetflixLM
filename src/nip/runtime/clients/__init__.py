"""Capability clients. Phase 1 ships the LLM client (text_llm, vlm, judge_llm), real and stub.

asr / ocr / detector / embedder / ner clients arrive with the deliverables that first call them
(2.5, 2.6, 2.8, 3.x); their Serve apps already deploy as placeholders (runtime.serving).
"""

from nip.contracts import Plan, Slot
from nip.runtime.catalog import Catalog
from nip.runtime.clients.llm import SERVE_URL, LLMClient, StubLLM

__all__ = ["SERVE_URL", "LLMClient", "StubLLM", "llm"]


def llm(plan: Plan, catalog: Catalog, slot: Slot, base_url: str = SERVE_URL) -> LLMClient | StubLLM:
    """Client for an LLM slot of the Plan: the stub backend when the slot resolved to a stub."""
    vid = plan.decisions[slot].variant
    engine = next(v.engine for v in catalog.variants if v.id == vid)
    return StubLLM(vid) if engine == "stub" else LLMClient(vid, base_url)
