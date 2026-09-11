import os
import tempfile
from pathlib import Path

import cv2

from pipeline.ingestion.normalizer.episode_document import Keyframe


def extract_keyframes(
    video_path: str,
    output_prefix: str,
    fps: float = 1.0,
    minio_client=None,
    bucket: str = "keyframes",
) -> list[Keyframe]:
    if not os.path.isfile(video_path):
        raise ValueError(f"Video file not found: {video_path}")

    output_dir = tempfile.mkdtemp(prefix=output_prefix.replace("/", "_"))
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        cap.release()
        raise ValueError(f"Invalid video FPS for: {video_path}")

    frame_interval = max(1, int(video_fps / fps))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    keyframes: list[Keyframe] = []
    frame_idx = 0

    while frame_idx < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        timecode = _frame_to_smpte(frame_idx, video_fps)
        filename = f"frame_{timecode.replace(':', '-')}.jpg"
        local_path = os.path.join(output_dir, filename)

        cv2.imwrite(local_path, frame)

        remote_path = f"{output_prefix}/{filename}"
        if minio_client is not None:
            minio_client.fput_object(bucket, remote_path, local_path)
            image_path = f"{bucket}/{remote_path}"
        else:
            image_path = local_path

        keyframes.append(Keyframe(image_path=image_path, timecode=timecode))
        frame_idx += frame_interval

    cap.release()
    return keyframes


def _frame_to_smpte(frame_number: int, fps: float) -> str:
    rounded_fps = round(fps)
    if rounded_fps <= 0:
        rounded_fps = 24

    total_seconds = frame_number // rounded_fps
    frames = int(frame_number % rounded_fps)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
