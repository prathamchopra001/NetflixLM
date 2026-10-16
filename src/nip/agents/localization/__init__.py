"""Localization Auditor. `CHECKS` lists its check classes; the pipeline imports this package and
builds the active ones (see `nip.pipeline`). 2.4 adds loc.term/shot_change/drift/offset here."""

from nip.agents.base import Check
from nip.agents.localization.readability import Readability

CHECKS: list[type[Check]] = [Readability]
