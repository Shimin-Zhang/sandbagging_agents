import pytest

from analyze import (accuracy, bootstrap_ci, coverage_by_cell, flip_rate,
                     paired_deltas, register_descriptives, require)


def mcq_row(model, qid, cell, correct, status="ok", source="truthfulqa"):
    return {"model": model, "qid": qid, "cell": cell, "correct": correct,
            "status": status, "source": source, "letter": "A", "variant": 0,
            "raw": "A", "usage": {}}


def test_accuracy_excludes_non_ok():
    rows = [mcq_row("m", "q1", "control", True),
            mcq_row("m", "q2", "control", False),
            mcq_row("m", "q3", "control", False, status="refusal")]
    assert accuracy(rows, "m", "control") == 0.5


def test_paired_deltas_and_bootstrap():
    rows = []
    for i in range(100):
        rows.append(mcq_row("m", f"q{i}", "edu-high", True))
        rows.append(mcq_row("m", f"q{i}", "edu-low", i >= 20))  # 20% worse
    deltas = paired_deltas(rows, "m", "edu-high", "edu-low")
    gap = sum(deltas) / len(deltas)
    assert abs(gap - 0.20) < 1e-9
    lo, hi = bootstrap_ci(deltas, n_boot=2000, seed=1)
    assert lo <= gap <= hi and hi - lo < 0.25


def test_flip_rate():
    rows = []
    for i in range(10):
        rows.append(mcq_row("m", f"q{i}", "control", i < 8))       # 8 correct
        rows.append(mcq_row("m", f"q{i}", "edu-low", i < 6))       # q6,q7 flip
    assert flip_rate(rows, "m", "edu-low") == 0.25  # 2 of 8 control-correct


def test_coverage_by_cell():
    jrows = [{"task": "coverage", "model": "m", "qid": "a", "key": "control",
              "cell": "control", "items": {"c1": True, "c2": True}},
             {"task": "coverage", "model": "m", "qid": "a", "key": "rough",
              "cell": "rough", "items": {"c1": True, "c2": False}}]
    cov = coverage_by_cell(jrows, "m")
    assert cov["control"] == 1.0 and cov["rough"] == 0.5


def test_register_descriptives_means_across_rows():
    rows = [{"model": "m", "cell": "control", "response": "w " * 10},
            {"model": "m", "cell": "control", "response": "w " * 20},
            {"model": "other", "cell": "control", "response": "w " * 99}]
    out = register_descriptives(rows, "m")
    assert out["control"]["mean_words"] == 15.0


def test_require_guards_empty_paired_data():
    with pytest.raises(SystemExit) as exc:
        require([], "arm1 edu-high/edu-low model=m source=truthfulqa")
    assert "arm1 edu-high/edu-low model=m source=truthfulqa" in str(exc.value)
    assert require([1], "whatever") == [1]


def test_pairwise_scores_and_position_bias():
    from analyze import first_shown_rate, pairwise_scores
    rows = []
    for qid, winners in [("q1", ["A", "A"]), ("q2", ["A", "tie"]), ("q3", ["B", "tie"])]:
        for order, w in enumerate(winners):
            rows.append({"task": "pairwise", "model": "m", "qid": qid,
                         "key": f"arm3-register:{order}", "pair": ["polished", "rough"],
                         "order": order, "winner": w})
    scores = pairwise_scores(rows)
    s, lo, hi, w, t, l = scores["arm3-register"]["m"]
    assert abs(s - ((1.0 + 0.5 - 0.5) / 3)) < 1e-9  # per-qid means: 1, .5, -.5
    assert w == 3 and t == 2 and l == 1
    assert lo <= s <= hi
    # decisive: q1 o0 A(first) q1 o1 A(not first) q2 o0 A(first) q3 o0 B(not first)
    assert first_shown_rate(rows) == 0.5
