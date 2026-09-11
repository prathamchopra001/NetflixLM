"""Script Critic Layer 3 - BDI character simulation (MVP stretch)."""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class BDISimulator:
    """Stub BDI character simulation layer. Disabled by default via feature flag."""

    def __init__(self) -> None:
        self._enabled = os.getenv("ENABLE_BDI_SIMULATION", "false").lower() == "true"

    def simulate_characters(self, show_id: str, episode_ref: str) -> list[dict]:
        """Simulate character belief-desire-intention models for the given episode."""
        if not self._enabled:
            return []

        logger.info("BDI simulation not yet implemented for show=%s episode=%s", show_id, episode_ref)
        return []
