"""Script Critic. `CHECKS` lists its check classes; the pipeline imports this package and builds the
active ones (see `nip.pipeline`). Layer 1 (2.3) = four SQL rules; Layer 2 checks are added later."""

from nip.agents.base import Check
from nip.agents.script_critic.layer1 import DeadActs, KnowledgeOrder, PropProvenance, TwoPlaces

CHECKS: list[type[Check]] = [KnowledgeOrder, DeadActs, TwoPlaces, PropProvenance]
