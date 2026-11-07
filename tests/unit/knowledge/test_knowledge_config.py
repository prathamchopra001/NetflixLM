"""The knowledge constants moved to config/pipeline.yaml (W-int) keep their shipped values."""

import inspect

from nip.knowledge import entities, extract, grounding, story


def test_knowledge_keys_keep_the_shipped_defaults() -> None:
    assert (extract.PROMPT_VERSION, extract.MAX_TOKENS) == ("knowledge.extract.v1", 2048)
    assert grounding.THRESHOLD == 90.0 and entities.RESOLVE_THRESHOLD == 90.0
    assert story._UNIT_DAYS == {"DAY": 1, "WEEK": 7, "MONTH": 30, "YEAR": 365}
    assert inspect.signature(story._excerpt).parameters["limit"].default == 600
    assert story._CFG["llm_max_tokens"] == 300
