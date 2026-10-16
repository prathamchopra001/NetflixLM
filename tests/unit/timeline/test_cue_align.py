"""Cue alignment (2.4): 1:1, 1:n and n:1 links, tracks with drift or an offset, the persisted
links (integration test in tests/integration/test_cue_align_pg.py)."""

import random
from fractions import Fraction

import pytest

from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Span, Timeline
from nip.timeline.cue_align import align, aligned, groups

Cue = tuple[float, float, str]


def tl(tracks: dict[str, list[Cue]], fps: Fraction = Fraction(24)) -> Timeline:
    spans = [
        Span(
            kind=EvidenceKind.SUBTITLE_CUE,
            ref=f"E1/{lang}/{i}",
            frames=(round(a * fps), round(b * fps)),
            lang=lang,
            text=t,
        )
        for lang, cues in tracks.items()
        for i, (a, b, t) in enumerate(cues, 1)
    ]
    return Timeline(
        episode="E1", fps=(fps.numerator, fps.denominator), duration_frames=10**6, spans=spans
    )


def source(n: int = 120, seed: int = 7) -> list[Cue]:
    """Cues with random gaps (0.9-3.5 s) and lengths (1.2-3 s), as in a real track."""
    rng, out, t = random.Random(seed), [], 1.0
    for i in range(n):
        d = rng.uniform(1.2, 3.0)
        out.append((t, t + d, f"s{i}"))
        t += d + rng.uniform(0.9, 3.5)
    return out


def translate(
    src: list[Cue], ratio: float = 1.0, shift: float = 0.0
) -> tuple[list[Cue], dict[int, set[int]]]:
    """A target track: every 10th pair of source cues merged into one cue, every 7th cue split in
    two, all times moved to `ratio * t + shift`. Also the truth: target number -> source numbers."""
    out: list[Cue] = []
    truth: dict[int, set[int]] = {}
    i = 0
    while i < len(src):
        a, b, _ = src[i]
        if i % 10 == 0 and i + 1 < len(src):
            out.append((ratio * a + shift, ratio * src[i + 1][1] + shift, f"t{i}"))
            truth[len(out)] = {i + 1, i + 2}
            i += 2
            continue
        if i % 7 == 0:
            mid = (a + b) / 2
            for lo, hi in ((a, mid - 0.05), (mid + 0.05, b)):
                out.append((ratio * lo + shift, ratio * hi + shift, f"t{i}"))
                truth[len(out)] = {i + 1}
        else:
            out.append((ratio * a + shift, ratio * b + shift, f"t{i}"))
            truth[len(out)] = {i + 1}
        i += 1
    return out, truth


def links(al_links: dict[str, tuple[str, ...]]) -> dict[int, set[int]]:
    return {
        int(t.rsplit("/", 1)[1]): {int(s.rsplit("/", 1)[1]) for s in ss}
        for t, ss in al_links.items()
    }


def test_one_to_one() -> None:
    cues = [(1, 3, "a"), (4, 6, "b")]
    al = align(tl({"en": cues, "es": cues}), "en", "es")
    assert al.links == {"E1/es/1": ("E1/en/1",), "E1/es/2": ("E1/en/2",)}


def test_split_and_merge_are_groups() -> None:
    # source 1 is split in two target cues (1:n); source 2 and 3 are one target cue (n:1)
    t = tl({"en": [(0, 4, "a"), (5, 6, "b"), (6.5, 8, "c")],
            "es": [(0, 1.9, "a1"), (2.1, 4, "a2"), (5, 8, "bc")]})  # fmt: skip
    al = align(t, "en", "es")
    assert al.links == {
        "E1/es/1": ("E1/en/1",),
        "E1/es/2": ("E1/en/1",),
        "E1/es/3": ("E1/en/2", "E1/en/3"),
    }
    gs = groups(al)
    assert [(g.sources, g.targets) for g in gs] == [
        (("E1/en/1",), ("E1/es/1", "E1/es/2")),
        (("E1/en/2", "E1/en/3"), ("E1/es/3",)),
    ]


def test_cue_overlapping_nothing_links_to_nothing() -> None:
    t = tl({"en": [(0, 2, "a"), (3, 5, "b"), (6, 8, "c")],
            "es": [(0, 2, "a"), (3, 5, "b"), (6, 8, "c"), (20, 22, "extra")]})  # fmt: skip
    al = align(t, "en", "es")
    assert al.links["E1/es/4"] == ()
    assert [g.targets for g in groups(al)] == [("E1/es/1",), ("E1/es/2",), ("E1/es/3",)]


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
def test_clean_translation_with_splits_and_merges(fps: Fraction) -> None:
    src = source()
    tgt, truth = translate(src, shift=0.08)
    al = align(tl({"en": src, "es": tgt}, fps), "en", "es")
    assert links(al.links) == truth
    assert al.fit is not None and abs(al.fit.slope) < 1e-3 and abs(al.fit.median_s - 0.08) < 0.1


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24000, 1001)])
@pytest.mark.parametrize("ratio", [25 / 24, 1000 / 1001, 1001 / 1000, 25025 / 24000])
def test_drifted_track_aligns_after_the_fit(fps: Fraction, ratio: float) -> None:
    """The drift (up to 4%: ~12 s at the end of 5 minutes) does not break the links."""
    src = source()
    tgt, truth = translate(src, ratio=ratio)
    al = align(tl({"en": src, "es": tgt}, fps), "en", "es")
    assert links(al.links) == truth
    assert al.fit is not None and abs(al.fit.slope - (ratio - 1)) < 2e-4


@pytest.mark.parametrize("shift", [-1.0, 0.5, 1.5])
def test_offset_track_aligns_and_reports_the_offset(shift: float) -> None:
    src = source()
    tgt, truth = translate(src, shift=shift)
    tgt = [(a, b, t) for a, b, t in tgt if a >= 0]  # a negative start cannot be a cue
    al = align(tl({"en": src, "es": tgt}), "en", "es")
    assert al.fit is not None and abs(al.fit.median_s - shift) < 0.1 and abs(al.fit.slope) < 5e-4
    got = links(al.links)
    assert all(got[t] == truth[t] for t in got)


def test_too_few_cues_have_no_fit() -> None:
    al = align(tl({"en": [(0, 2, "a")], "es": [(0, 2, "a")]}), "en", "es")
    assert al.fit is None and al.links == {"E1/es/1": ("E1/en/1",)}  # plain overlap
    assert align(tl({"en": [(0, 2, "a")]}), "en", "es").links == {}


def test_aligned_is_remembered_per_timeline() -> None:
    t = tl({"en": source(), "es": source()})
    assert aligned(t, "en", "es") is aligned(t, "en", "es")
    assert aligned(tl({"en": source(), "es": source()}), "en", "es") is not aligned(t, "en", "es")
