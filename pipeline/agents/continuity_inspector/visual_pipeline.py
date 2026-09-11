"""Continuity Inspector - visual CV + VLM pipeline for visual continuity errors."""

import base64
import httpx
from typing import Any


class VisualPipeline:
    """Sends flagged keyframe pairs to VLM (Qwen2-VL) for visual continuity analysis."""

    def __init__(self, llm_url: str, cv_service_url: str | None = None) -> None:
        self._llm_url = llm_url
        self._cv_service_url = cv_service_url

    def detect_visual_continuity(self, keyframe_pairs: list[dict]) -> list[dict]:
        """Batch VLM analysis of keyframe pairs, return ContinuityFlag dicts."""
        flags: list[dict] = []
        for pair in keyframe_pairs:
            result = self.analyze_keyframe_pair(
                frame_a_path=pair["frame_a"],
                frame_b_path=pair["frame_b"],
                scene_context=pair.get("scene_context", {}),
            )
            if result.get("issues"):
                import uuid

                for issue in result["issues"]:
                    flags.append({
                        "id": str(uuid.uuid4()),
                        "issue": issue.get("description", "Visual continuity error"),
                        "severity": issue.get("severity", "medium"),
                        "signal_source": "visual_cv_vlm",
                        "evidence": issue.get("evidence", []),
                        "confidence": issue.get("confidence", 0.75),
                        "script_version": pair.get("episode_ref", ""),
                    })
        return flags

    def analyze_keyframe_pair(
        self,
        frame_a_path: str,
        frame_b_path: str,
        scene_context: dict,
    ) -> dict:
        """Single pair VLM analysis. Returns continuity assessment dict."""
        frame_a_b64 = self._encode_image(frame_a_path)
        frame_b_b64 = self._encode_image(frame_b_path)

        prompt = (
            "Compare these two keyframes from the same scene. "
            "Identify any visual continuity errors such as: "
            "props appearing/disappearing, costume changes, lighting shifts, "
            "character position jumps, or set dressing differences.\n\n"
            f"Scene context: {scene_context}\n\n"
            "Respond as JSON: {\"issues\": [{\"description\": str, "
            "\"severity\": str, \"evidence\": list, \"confidence\": float}]}"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_a_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_b_b64}"}},
                ],
            }
        ]

        response = self._call_vlm(messages)
        return self._parse_vlm_response(response)

    def _call_vlm(self, messages: list[dict]) -> str:
        resp = httpx.post(
            f"{self._llm_url}/v1/chat/completions",
            json={"model": "Qwen/Qwen2-VL-7B-Instruct", "messages": messages, "temperature": 0.05},
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _parse_vlm_response(response: str) -> dict:
        import json

        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"issues": []}
