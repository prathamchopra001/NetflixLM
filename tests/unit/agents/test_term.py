"""loc.term (2.4): approved and observed-standard renderings in the aligned target cues."""

from fractions import Fraction

import pytest

from nip.agents.base import Input, run_check
from nip.agents.localization import CHECKS
from nip.agents.localization.term import Entry, Term, has_all, inflected, mentions
from nip.contracts.flag import EvidenceKind, EvidenceRole, Flag, ProducedBy, Tier
from nip.contracts.timeline import Span, Timeline

PB = ProducedBy(model_variant=None, plan_id="plan_1")
Cue = tuple[float, float, str]

DRAGON = Entry("dragon", {"es": ["dragón"]})
HOLLOW = Entry("the Hollow", {"es-419": ["el Hueco"]})  # glossary tagged es-419, track tagged es
MEMORY = Entry("memory overwrite", {"es": ["Sobreescritura de la memoria"]})
SINTEL = Entry("Sintel", {"es": ["Sintel"]})
WREN = Entry("Wren")  # a bible name: no approved rendering


def tl(en: list[Cue], es: list[Cue], fps: Fraction = Fraction(24)) -> Timeline:
    spans = [
        Span(
            kind=EvidenceKind.SUBTITLE_CUE,
            ref=f"E1/{lang}/{i}",
            frames=(round(a * fps), round(b * fps)),
            lang=lang,
            text=t,
        )
        for lang, cues in (("en", en), ("es", es))
        for i, (a, b, t) in enumerate(cues, 1)
    ]
    return Timeline(
        episode="E1", fps=(fps.numerator, fps.denominator), duration_frames=10**6, spans=spans
    )


def flags(t: Timeline, registry: list[Entry]) -> list[Flag]:
    return run_check(Term(["es"], "en", registry=registry), t, "run_1", PB)


def one(src: str, tgt: str, entry: Entry, fps: Fraction = Fraction(24)) -> list[Flag]:
    """A source cue and its target cue (with two filler cues around, as a real track has)."""
    en = [(0, 2, "Hello."), (3, 5, src), (6, 8, "Bye.")]
    es = [(0, 2, "Hola."), (3, 5, tgt), (6, 8, "Adiós.")]
    return flags(tl(en, es, fps), [entry])


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
@pytest.mark.parametrize(
    ("src", "tgt", "entry", "conf", "what"),
    [
        ("The dragon sleeps.", "La serpiente alada duerme.", DRAGON, 0.80, "is missing"),
        ("The dragon sleeps.", "El dragon duerme.", DRAGON, 0.92, "near miss"),  # accent lost
        ("Enter the Hollow.", "Entra en el Hueko.", HOLLOW, 0.92, "near miss"),
        ("Enter the Hollow.", "Entra en el Vacío.", HOLLOW, 0.80, "is missing"),
        (
            "Run memory overwrite.",
            "Ejecuta Sobrescritura de la memoria.",
            MEMORY,
            0.92,
            "near miss",
        ),
        ("Run memory overwrite.", "Ejecuta Sobreescritura memoria.", MEMORY, 0.80, "is missing"),
        ("Run memory overwrite.", "Ejecuta Sobreescritura de memoria.", MEMORY, 0.80, "is missing"),
        ("Sintel runs.", "Cintel corre.", SINTEL, 0.92, "near miss"),
        ("Sintel runs.", "Sintell corre.", SINTEL, 0.92, "near miss"),  # a name has no inflection
    ],
)
def test_planted_term_errors(
    src: str, tgt: str, entry: Entry, conf: float, what: str, fps: Fraction
) -> None:
    (flag,) = one(src, tgt, entry, fps)
    assert (flag.check, flag.lang, flag.confidence) == ("loc.term", "es", conf)
    assert what in flag.explanation
    assert flag.title.startswith("Cue 2:")
    claims = [(e.ref, e.role) for e in flag.evidence if e.role is EvidenceRole.CLAIM]
    assert claims == [("E1/es/2", EvidenceRole.CLAIM)]
    assert ("E1/en/2", EvidenceRole.CONTEXT) in [(e.ref, e.role) for e in flag.evidence]
    assert flag.tier is (Tier.MUST_REVIEW if conf >= 0.9 else Tier.REVIEW_RECOMMENDED)


@pytest.mark.parametrize(
    ("src", "tgt", "entry"),
    [
        ("The dragon sleeps.", "El dragón duerme.", DRAGON),
        ("The dragons sleep.", "Los dragones duermen.", DRAGON),  # inflection of a common noun
        ("The dragon sleeps.", "Duerme el DRAGÓN.", DRAGON),  # case
        ("Enter the Hollow.", "Entra en el Hueco.", HOLLOW),  # es-419 pack serves an es track
        ("Run memory overwrite.", "Ejecuta Sobreescritura de la memoria.", MEMORY),
        ("Sintel runs.", "Sintel corre.", SINTEL),
        ("Nothing here.", "Nada aquí.", DRAGON),  # the term is not in the source
    ],
)
def test_correct_renderings_are_not_flagged(src: str, tgt: str, entry: Entry) -> None:
    assert one(src, tgt, entry) == []


def test_source_side_is_loose_but_content_words_are_whole_words() -> None:
    have = ["the", "dragons", "sleep"]
    assert mentions("dragon", have) and mentions("Dragon", have)
    assert not mentions("dragon", ["dragonflies"])  # 5 more letters: a different word
    assert not mentions("dragon", ["the", "dragoon"])


def test_inflection_needs_a_stem_of_five_and_a_short_ending() -> None:
    assert inflected("dragón", "dragones") and inflected("guardianes", "guardián")
    assert not inflected(
        "dragón", "dragón"
    )  # same word: not an inflection (exact is handled first)
    assert not inflected("capitán", "capitan")  # an accent alone is a misspelling
    assert not inflected("casa", "casas")  # stem under 5 letters
    assert not inflected("hueco", "huecoabcd")  # ending over 3 letters


def test_phrase_must_be_intact() -> None:
    assert has_all(
        "Sobreescritura de la memoria", "ejecuta sobreescritura de la memoria".split(), False
    )
    assert not has_all("Sobreescritura de la memoria", "sobreescritura memoria".split(), False)
    assert not has_all("Sobreescritura de la memoria", "memoria de sobreescritura".split(), False)


def test_split_and_merged_cues_are_checked_as_a_group() -> None:
    # 1:n: one source cue, the rendering is in the second of two target cues
    en = [(0, 4, "The dragon sleeps here.")]
    es = [(0, 1.9, "Aquí duerme"), (2.1, 4, "el dragón.")]
    assert flags(tl(en, es), [DRAGON]) == []
    es_bad = [(0, 1.9, "Aquí duerme"), (2.1, 4, "el bicho.")]
    (flag,) = flags(tl(en, es_bad), [DRAGON])
    assert [e.ref for e in flag.evidence if e.role is EvidenceRole.CLAIM] == ["E1/es/1", "E1/es/2"]
    # n:1: two source cues, one target cue
    en = [(0, 2, "The dragon"), (2.2, 4, "sleeps here.")]
    assert flags(tl(en, [(0, 4, "El dragón duerme aquí.")]), [DRAGON]) == []
    assert len(flags(tl(en, [(0, 4, "El bicho duerme aquí.")]), [DRAGON])) == 1


def test_a_big_group_is_ambiguous() -> None:
    en = [(0, 4, "The dragon sleeps here.")]
    es = [(0, 1.2, "Aquí"), (1.3, 2.5, "duerme"), (2.6, 4, "el bicho.")]  # 3 target cues
    (flag,) = flags(tl(en, es), [DRAGON])
    assert flag.confidence == 0.65 and flag.tier is Tier.SUPPRESSED


def _tour(kept: int, dropped: int) -> Timeline:
    """`kept` cues that say Wren in both tracks, `dropped` that lose it in the target."""
    en = [(3 * i, 3 * i + 2, "Wren runs.") for i in range(kept + dropped)]
    es = [
        (3 * i, 3 * i + 2, "Wren corre." if i < kept else "Corre.") for i in range(kept + dropped)
    ]
    return tl(en, es)


def test_observed_standard_flags_the_odd_cue_below_review_confidence() -> None:
    fl = flags(_tour(kept=4, dropped=1), [WREN])
    assert [(f.title, f.confidence, f.tier, f.severity) for f in fl] == [
        ('Cue 5: "Wren" should be "Wren"', 0.55, Tier.SUPPRESSED, 2)
    ]
    assert "Ambiguous" in fl[0].explanation


def test_observed_standard_needs_a_majority_and_enough_cues() -> None:
    assert len(flags(_tour(kept=2, dropped=1), [WREN])) == 1  # 3 mentions, 2 kept (67% >= 60%)
    assert flags(_tour(kept=1, dropped=2), [WREN]) == []  # 33%: not the standard
    assert flags(_tour(kept=1, dropped=1), [WREN]) == []  # fewer than 3 mentions


def test_misspelled_observed_name_is_a_near_miss() -> None:
    en = [(3 * i, 3 * i + 2, "Wren runs.") for i in range(5)]
    es = [(3 * i, 3 * i + 2, "Wren corre.") for i in range(4)] + [(12, 14, "Wrenn corre.")]
    (flag,) = flags(tl(en, es), [WREN])
    assert flag.confidence == 0.85 and "near miss" in flag.explanation


def test_a_name_that_is_always_translated_has_no_standard() -> None:
    en = [(3 * i, 3 * i + 2, "The Shaman waits.") for i in range(5)]
    es = [(3 * i, 3 * i + 2, "El Chamán espera.") for i in range(5)]
    assert flags(tl(en, es), [Entry("The Shaman")]) == []


def test_approved_rendering_beats_the_observed_standard() -> None:
    entry = Entry("Wren", {"es": ["Reyezuelo"]})
    fl = flags(_tour(kept=4, dropped=1), [entry])  # 'Wren' in 4 cues is not the approved rendering
    assert [(f.confidence, f.severity) for f in fl] == [(0.80, 3)] * 5


def test_recheck_passes_then_fails_after_the_fix() -> None:
    check = Term(["es"], "en", registry=[DRAGON])
    bad = tl([(0, 2, "The dragon sleeps.")], [(0, 2, "El bicho duerme.")])
    (flag,) = run_check(check, bad, "run_1", PB)
    assert check.recheck(flag, bad) is True
    fixed = tl([(0, 2, "The dragon sleeps.")], [(0, 2, "El dragón duerme.")])
    assert check.recheck(flag, fixed) is False
    other = tl([(0, 2, "Nothing.")], [(0, 2, "El bicho duerme.")])
    assert check.recheck(flag, other) is False


def test_needs_subtitles_and_a_registry() -> None:
    both = {Input.SOURCE_SUBS, Input.TARGET_SUBS}
    assert Term in CHECKS
    assert not Term.active(both)
    assert Term.active(both | {Input.GLOSSARY}) and Term.active(both | {Input.BIBLE})
    assert not Term.active({Input.GLOSSARY, Input.BIBLE, Input.TARGET_SUBS})


def test_no_registry_checks_nothing(caplog: pytest.LogCaptureFixture) -> None:
    t = tl([(0, 2, "The dragon.")], [(0, 2, "El bicho.")])
    with caplog.at_level("WARNING"):
        assert run_check(Term(["es"], "en"), t, "run_1", PB) == []
    assert "no registry" in caplog.text


def test_units_follow_cue_windows_and_hold_the_aligned_source_cues() -> None:
    en = [(3 * i, 3 * i + 2, f"Line {i}.") for i in range(25)]
    es = [(3 * i, 3 * i + 2, f"Línea {i}.") for i in range(25)]
    units = Term(["es"], "en", registry=[DRAGON]).units(tl(en, es))
    assert [u.key for u in units] == ["E1/es/1-20", "E1/es/21-25"]
    assert [s.ref for s in units[1].context] == [f"E1/en/{i}" for i in range(21, 26)]
