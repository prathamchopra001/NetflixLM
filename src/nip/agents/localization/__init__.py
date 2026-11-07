"""Localization Auditor. `CHECKS` lists its check classes; the pipeline imports this package and
builds the active ones (see `nip.pipeline`)."""

from nip.agents.base import Check
from nip.agents.localization.drift import Drift, Offset
from nip.agents.localization.readability import Readability
from nip.agents.localization.shot_change import ShotChange
from nip.agents.localization.term import Term

CHECKS: list[type[Check]] = [Readability, Term, ShotChange, Drift, Offset]
