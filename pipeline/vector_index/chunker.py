"""
chunker.py
Scene-level chunking for EpisodeDocuments.  
Each scene becomes one chunk; long scenes (>2000 tokens) are sub-chunked with 200-token overlap.
Returns dicts conforming to the VectorIndexChunk schema defined in docs/data-schemas.md.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Sequence

import tiktoken


# Configuration constants per schema spec and project conventions
MAX_TOKENS = 2000
OVERLAP_TOKENS = 200
ENCODING_NAME = "cl100k_base"


@dataclass
class Chunk:
    """Represents a single chunk ready for embedding."""
    chunk_id: str
    episode_ref: str
    scene_id: str
    text: str
    embedding_model: str = ""  # filled at embed time
    metadata: dict = field(default_factory=dict)


def _episode_ref(show_id: str, season: int, episode: int) -> str:
    """e.g. 'stranger-things' S3E5 → 'S3E5'."""
    return f"S{season}E{episode}"


def _build_chunk_id(episode_ref: str, scene_id: str, idx: int) -> str:
    """For a scene split into multiple chunks, e.g.  S3E5_Sc03_001."""
    return f"{episode_ref}_{scene_id}_{idx:03d}"


def _count_tokens(text: str) -> int:
    try:
        enc = tiktoken.get_encoding(ENCODING_NAME)
        return len(enc.encode(text))
    except Exception:
        # Rough fallback: ~4 chars per token
        return len(text) // 4


def _sub_chunk(text: str, max_tokens: int, overlap_tokens: int) -> list[tuple[str, int]]:
    """
    Split a long text into overlapping sub-chunks.
    Returns list of (sub_text, start_position).
    """
    try:
        enc = tiktoken.get_encoding(ENCODING_NAME)
        tokens = enc.encode(text)
    except Exception:
        # Word-based fallback
        words = text.split()
        out, start = [], 0
        while start < len(words):
            sub = words[start : start + max_tokens]
            out.append((" ".join(sub), start))
            start += max(max_tokens - overlap_tokens, 1)
        return out

    out, start = [], 0
    total = len(tokens)
    while start < total:
        end = min(start + max_tokens, total)
        sub_tokens = tokens[start:end]
        sub_text = enc.decode(sub_tokens)
        out.append((sub_text, start))
        step = max(max_tokens - overlap_tokens, 1)
        start += step
        if end >= total:
            break
    return out


def _extract_scene_text(scene: dict) -> str:
    """Flatten a scene's script_block into a single text string."""
    parts: list[str] = []
    block = scene.get("script_block", {})
    loc = block.get("location", "")
    if loc:
        parts.append(f"Location: {loc}")
    tod = block.get("time_of_day", "")
    if tod:
        parts.append(f"Time: {tod}")
    chars = block.get("characters_present", [])
    if chars:
        parts.append(f"Characters: {', '.join(chars)}")
    for line in block.get("dialogue", []):
        c = line.get("character", "")
        l = line.get("line", "")
        d = line.get("direction", "")
        parts.append(f"{c}: {l}" + (f" [{d}]" if d else ""))
    sd = block.get("stage_directions", "")
    if sd:
        parts.append(sd)
    # Also include transcript text if present
    ts = scene.get("transcript_segment", {})
    if isinstance(ts, dict) and ts.get("text"):
        parts.append(ts["text"])
    return "\n".join(parts)


def chunk_episode(episode: dict) -> list[Chunk]:
    """
    Given an EpisodeDocument dict, return a list of Chunk objects.
    Scene-level by default; long scenes are sub-chunked.
    """
    show_id = episode.get("show_id", "")
    season = episode.get("season", 1)
    episode_num = episode.get("episode", 1)
    ep_ref = _episode_ref(show_id, season, episode_num)
    timeline = episode.get("timeline", []) or []

    chunks: list[Chunk] = []
    for entry in timeline:
        scene_id = entry.get("scene_id", "")
        timecode = entry.get("timecode", "")
        text = _extract_scene_text(entry)
        token_count = _count_tokens(text)

        # metadata per schema
        block = entry.get("script_block", {})
        chars_present = block.get("characters_present", [])
        loc = block.get("location", "")

        base_meta = {
            "show_id": show_id,
            "season": season,
            "episode": episode_num,
            "scene_characters": chars_present,
            "scene_location": loc,
            "timecode_start": timecode,
            "timecode_end": timecode,
            "chunk_type": "scene",
        }

        if token_count <= MAX_TOKENS:
            chunk_id = _build_chunk_id(ep_ref, scene_id, 1)
            chunks.append(Chunk(chunk_id=chunk_id, episode_ref=ep_ref, scene_id=scene_id, text=text, metadata=base_meta))
        else:
            sub_chunks = _sub_chunk(text, MAX_TOKENS, OVERLAP_TOKENS)
            for sub_idx, (sub_text, _) in enumerate(sub_chunks, start=1):
                meta = {**base_meta, "chunk_type": "sub_scene", "parent_scene": scene_id}
                chunk_id = _build_chunk_id(ep_ref, scene_id, sub_idx)
                chunks.append(Chunk(chunk_id=chunk_id, episode_ref=ep_ref, scene_id=scene_id, text=sub_text, metadata=meta))
    return chunks
