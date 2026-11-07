"""Deterministic synthetic multi-episode show with exact ground truth (R2, no LLM)."""

from eval.synthetic.generate import build
from eval.synthetic.model import Show, read_show, write_show

__all__ = ["Show", "build", "read_show", "write_show"]
