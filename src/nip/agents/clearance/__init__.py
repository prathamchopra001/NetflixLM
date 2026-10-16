"""Clearance Scanner. 2.6 ships the on-screen-text channel (`ocr_text`); matching, occurrences and
flags (`CHECKS`) arrive with 2.7."""

from nip.agents.base import Check

CHECKS: list[type[Check]] = []
