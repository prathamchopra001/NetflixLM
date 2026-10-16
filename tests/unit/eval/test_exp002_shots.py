import json

from eval.exp.exp002_shots import apply_mask, cut_metrics, load_truth, match_cuts


def test_match_within_tolerance_one_to_one():
    # 101~100 and 198~200 match (|d| <= 2); 304 is 3 from 301, no match; no pred is reused
    tp, fp, fn, offs = match_cuts([101, 198, 304, 500], [100, 200, 300, 301], tol=2)
    assert (tp, fp, fn) == (2, 2, 2)
    assert sorted(offs) == [-2, 1]
    assert match_cuts([100], [99, 101], tol=2)[:3] == (1, 0, 1)  # single pred, two labels


def test_metrics_and_mask():
    m = cut_metrics([10, 50, 90, 400], [10, 52, 200], tol=2, mask=[(380, 420)])
    # masked: pred 400 dropped; 10, 52 match; 90 is FP; 200 is FN
    assert (m["shown/tp/all"], m["shown/fp/all"], m["shown/fn/all"]) == (2, 1, 1)
    assert m["shown/f1/all"] == 2 * (2 / 3) * (2 / 3) / (4 / 3)
    assert m["unmasked/fp/all"] == 2  # unmasked keeps the 400
    assert m["shown/f1_tol0/all"] < m["shown/f1/all"]  # 50 vs 52 only matches with tolerance


def test_empty_and_helpers(tmp_path):
    assert cut_metrics([], [])["shown/f1/all"] == 0.0
    assert apply_mask([1, 5, 9], [(4, 6)]) == [1, 9]
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"cuts": [9, 3]}))
    assert load_truth(p) == [3, 9]
