from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DialogueLine:
    character: str
    line: str
    direction: str = ""


@dataclass
class SceneBlock:
    scene_id: str = ""
    location: str = ""
    time_of_day: str = ""
    characters_present: list[str] = field(default_factory=list)
    dialogue: list[DialogueLine] = field(default_factory=list)
    stage_directions: str = ""


@dataclass
class SubtitleSegment:
    text: str
    start_tc: str
    end_tc: str


@dataclass
class Keyframe:
    image_path: str
    timecode: str
    scene_id: str = ""


@dataclass
class SceneEntry:
    timecode: str
    scene_id: str
    script_block: Dict[str, Any] = field(default_factory=dict)
    transcript_segment: Dict[str, Any] = field(default_factory=dict)
    keyframe: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeDocument:
    show_id: str
    season: int
    episode: int
    script_version: str
    timeline: List[SceneEntry] = field(default_factory=list)
    show_metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_to_episode_document(raw_data: Dict[str, Any]) -> EpisodeDocument:
    timeline = raw_data.get("timeline", [])
    scenes = [SceneEntry(**scene) for scene in timeline]
    return EpisodeDocument(
        show_id=raw_data.get("show_id", ""),
        season=raw_data.get("season", 0),
        episode=raw_data.get("episode", 0),
        script_version=raw_data.get("script_version", ""),
        timeline=scenes,
        show_metadata=raw_data.get("show_metadata", {}),
    )


def build_episode_document(
    show_id: str,
    season: int,
    episode: int,
    script_version: str,
    scene_blocks: list[SceneBlock],
    subtitle_segments: list[SubtitleSegment],
    keyframes: list[Keyframe],
    scene_timecode_map: Optional[Dict[str, tuple[str, str]]] = None,
    show_metadata: Optional[Dict[str, Any]] = None,
) -> EpisodeDocument:
    timeline: List[SceneEntry] = []
    kf_by_tc: Dict[str, Keyframe] = {kf.timecode: kf for kf in keyframes}
    sub_by_start_tc: Dict[str, SubtitleSegment] = {s.start_tc: s for s in subtitle_segments}

    if scene_timecode_map is None:
        scene_timecode_map = {}

    for block in scene_blocks:
        sid = block.scene_id
        start_tc, end_tc = scene_timecode_map.get(sid, ("00:00:00:00", "00:00:00:00"))

        script_dict = {
            "scene_id": block.scene_id,
            "location": block.location,
            "time_of_day": block.time_of_day,
            "characters_present": block.characters_present,
            "dialogue": [{"character": d.character, "line": d.line, "direction": d.direction} for d in block.dialogue],
            "stage_directions": block.stage_directions,
        }

        transcript_dict: Dict[str, Any] = {}
        for tc_key in (start_tc,):
            seg = sub_by_start_tc.get(tc_key)
            if seg:
                transcript_dict = {"text": seg.text, "start_tc": seg.start_tc, "end_tc": seg.end_tc}

        keyframe_dict: Dict[str, Any] = {}
        kf = kf_by_tc.get(start_tc)
        if kf:
            keyframe_dict = {"image_path": kf.image_path, "timecode": kf.timecode, "scene_id": kf.scene_id}

        timeline.append(
            SceneEntry(
                timecode=start_tc,
                scene_id=sid,
                script_block=script_dict,
                transcript_segment=transcript_dict,
                keyframe=keyframe_dict,
            )
        )

    return EpisodeDocument(
        show_id=show_id,
        season=season,
        episode=episode,
        script_version=script_version,
        timeline=timeline,
        show_metadata=show_metadata or {},
    )
