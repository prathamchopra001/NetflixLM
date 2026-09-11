from difflib import SequenceMatcher
from typing import Dict, Optional

from pipeline.ingestion.normalizer.episode_document import (
    Keyframe,
    SceneBlock,
    SceneEntry,
    SubtitleSegment,
)

SIMILARITY_THRESHOLD = 0.5
SECONDS_PER_SCENE = 30
FRAMES_PER_SECOND = 24


def align_timeline(
    scene_blocks: list[SceneBlock],
    transcripts: list[SubtitleSegment],
    keyframes: list[Keyframe],
) -> list[SceneEntry]:
    scene_ranges = _assign_timecode_ranges(scene_blocks)
    transcript_map = _assign_transcripts_to_scenes(transcripts, scene_blocks, scene_ranges)
    keyframe_map = _assign_keyframes_to_scenes(keyframes, scene_ranges)

    all_timecodes = _collect_all_timecodes(transcripts, keyframes, scene_ranges)
    if not all_timecodes:
        return []

    entries: list[SceneEntry] = []
    for tc in sorted(all_timecodes):
        scene_id = _find_scene_for_timecode(tc, scene_ranges)
        if scene_id is None:
            continue

        script_dict = _serialize_script_block(scene_id, scene_blocks, scene_ranges)
        entry = SceneEntry(
            timecode=tc,
            scene_id=scene_id,
            script_block=script_dict,
            transcript_segment=transcript_map.get(tc, {}),
            keyframe=keyframe_map.get(tc, {}),
        )
        entries.append(entry)

    return entries


def _assign_timecode_ranges(
    scene_blocks: list[SceneBlock],
) -> Dict[str, tuple[str, str]]:
    ranges: Dict[str, tuple[str, str]] = {}
    current_frame = 0

    for block in scene_blocks:
        sid = block.scene_id
        dialogue_count = max(len(block.dialogue), 1)
        duration_frames = dialogue_count * SECONDS_PER_SCENE * FRAMES_PER_SECOND
        start_frame = current_frame
        end_frame = start_frame + duration_frames - 1
        start_tc = _frame_to_smpte(start_frame, FRAMES_PER_SECOND)
        end_tc = _frame_to_smpte(end_frame, FRAMES_PER_SECOND)
        ranges[sid] = (start_tc, end_tc)
        current_frame = end_frame + 1

    return ranges


def _assign_transcripts_to_scenes(
    transcripts: list[SubtitleSegment],
    scene_blocks: list[SceneBlock],
    scene_ranges: Dict[str, tuple[str, str]],
) -> Dict[str, dict]:
    result: Dict[str, dict] = {}

    for seg in transcripts:
        scene_id = _find_scene_for_timecode(seg.start_tc, scene_ranges)
        best_ratio = 0.0

        if scene_id:
            block = _find_script_block(scene_id, scene_blocks, scene_ranges)
            if block:
                for dl in block.dialogue:
                    ratio = SequenceMatcher(None, seg.text.lower(), dl.line.lower()).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio

        if best_ratio >= SIMILARITY_THRESHOLD or best_ratio == 0.0:
            result[seg.start_tc] = {"text": seg.text, "start_tc": seg.start_tc, "end_tc": seg.end_tc}
        else:
            result[seg.start_tc] = {"text": seg.text, "start_tc": seg.start_tc, "end_tc": seg.end_tc}

    return result


def _assign_keyframes_to_scenes(
    keyframes: list[Keyframe],
    scene_ranges: Dict[str, tuple[str, str]],
) -> Dict[str, dict]:
    result: Dict[str, dict] = {}
    for kf in keyframes:
        scene_id = _find_scene_for_timecode(kf.timecode, scene_ranges)
        kf_dict = {"image_path": kf.image_path, "timecode": kf.timecode}
        if scene_id:
            kf_dict["scene_id"] = scene_id
        result[kf.timecode] = kf_dict
    return result


def _collect_all_timecodes(
    transcripts: list[SubtitleSegment],
    keyframes: list[Keyframe],
    scene_ranges: Dict[str, tuple[str, str]],
) -> set[str]:
    tcs: set[str] = set()
    for seg in transcripts:
        tcs.add(seg.start_tc)
    for kf in keyframes:
        tcs.add(kf.timecode)
    for start_tc, _ in scene_ranges.values():
        tcs.add(start_tc)
    return tcs


def _find_scene_for_timecode(
    tc: str,
    scene_ranges: Dict[str, tuple[str, str]],
) -> Optional[str]:
    tc_frames = _smpte_to_frames(tc)
    for scene_id, (start_tc, end_tc) in scene_ranges.items():
        start_frames = _smpte_to_frames(start_tc)
        end_frames = _smpte_to_frames(end_tc)
        if start_frames <= tc_frames <= end_frames:
            return scene_id
    return None


def _find_script_block(
    scene_id: str,
    scene_blocks: list[SceneBlock],
    scene_ranges: Dict[str, tuple[str, str]],
) -> Optional[SceneBlock]:
    keys = list(scene_ranges.keys())
    if scene_id in keys:
        idx = keys.index(scene_id)
        if idx < len(scene_blocks):
            return scene_blocks[idx]
    return None


def _serialize_script_block(
    scene_id: str,
    scene_blocks: list[SceneBlock],
    scene_ranges: Dict[str, tuple[str, str]],
) -> dict:
    block = _find_script_block(scene_id, scene_blocks, scene_ranges)
    if block is None:
        return {}
    return {
        "scene_id": block.scene_id,
        "location": block.location,
        "time_of_day": block.time_of_day,
        "characters_present": block.characters_present,
        "dialogue": [
            {"character": d.character, "line": d.line, "direction": d.direction}
            for d in block.dialogue
        ],
        "stage_directions": block.stage_directions,
    }


def _smpte_to_frames(tc: str) -> int:
    h, m, s, f = tc.split(":")
    return int(h) * 3600 * FRAMES_PER_SECOND + int(m) * 60 * FRAMES_PER_SECOND + int(s) * FRAMES_PER_SECOND + int(f)


def _frame_to_smpte(frame: int, fps: int) -> str:
    f = frame % fps
    total_seconds = frame // fps
    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"
