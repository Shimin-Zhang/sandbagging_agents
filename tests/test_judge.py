import json

import pytest

from common import read_jsonl
from judge import (PAIRS, coverage_prompt, judge_all, pairwise_prompt,
                   parse_json_reply, restrict_judge, rubric_prompt)

Q = {"qid": "aq1", "domain": "health", "smoke": True,
     "phrasings": {"lay-polished": "CANONICAL QUESTION", "jargon-polished": "JARGON Q",
                    "lay-rough": "rough q", "jargon-rough": "jargon rough q"},
     "substitutions": [["x", "y"]],
     "checklist": [{"id": "c1", "tag": "warning", "text": "warns about z"},
                    {"id": "c2", "tag": "fact", "text": "states w"}]}

BIO_ANSWER = {"model": "sonnet", "qid": "aq1", "cell": "edu-low", "variant": 0,
              "response": "ANSWER TEXT", "usage": {}}
JARGON_ANSWER = {"model": "sonnet", "qid": "aq1", "cell": "jargon-rough", "variant": None,
                 "response": "JARGON ANSWER", "usage": {}}


def test_blinding_uses_canonical_question_and_no_bio():
    for row in [BIO_ANSWER, JARGON_ANSWER]:
        p = coverage_prompt(Q, row)
        assert "CANONICAL QUESTION" in p
        assert "JARGON Q" not in p and "jargon rough q" not in p
        assert "edu-low" not in p and "Danny" not in p


def test_coverage_prompt_lists_items():
    p = coverage_prompt(Q, BIO_ANSWER)
    assert "c1: warns about z" in p and "c2: states w" in p


def test_parse_json_reply_handles_fences():
    assert parse_json_reply('```json\n{"c1": true}\n```') == {"c1": True}
    assert parse_json_reply('noise {"winner": "A"} trailing') == {"winner": "A"}


def test_pairwise_prompt_orders():
    p0 = pairwise_prompt(Q, "ans-polished", "ans-rough", order=0)
    p1 = pairwise_prompt(Q, "ans-polished", "ans-rough", order=1)
    assert p0.index("ans-polished") < p0.index("ans-rough")
    assert p1.index("ans-rough") < p1.index("ans-polished")


class FakeJudge:
    def chat(self, model, messages, max_tokens=1024, **kwargs):
        text = messages[0]["content"]
        if "checklist" in text.lower():
            return json.dumps({"c1": True, "c2": False}), {}
        if "1-7" in text:
            return json.dumps({"factual_correctness": 6, "completeness": 5,
                               "actionability": 6, "appropriate_caution": 7}), {}
        return json.dumps({"winner": "tie"}), {}


def test_judge_all_counts(tmp_path):
    out = str(tmp_path / "judge.jsonl")
    answers = []
    for cell in ["control", "edu-high", "edu-low", "polished", "rough",
                 "jargon-polished", "lay-rough", "jargon-rough"]:
        answers.append({"model": "sonnet", "qid": "aq1", "cell": cell,
                        "variant": None, "response": f"ans-{cell}", "usage": {}})
    judge_all([Q], answers, FakeJudge(), out)
    rows = read_jsonl(out)
    n_cov = sum(r["task"] == "coverage" for r in rows)
    n_rub = sum(r["task"] == "rubric" for r in rows)
    n_pw = sum(r["task"] == "pairwise" for r in rows)
    assert n_cov == 8 and n_rub == 8
    assert n_pw == len(PAIRS) * 2  # both orders
    assert all(r.get("prompt") for r in rows)
    assert all(r.get("raw") for r in rows)
    cov_row = next(r for r in rows if r["task"] == "coverage")
    assert cov_row["raw"] == json.dumps({"c1": True, "c2": False})
    # rerun is a no-op
    judge_all([Q], answers, FakeJudge(), out)
    assert len(read_jsonl(out)) == len(rows)


def test_judge_all_workers3_same_row_multiset(tmp_path):
    answers = []
    for cell in ["control", "edu-high", "edu-low", "polished", "rough",
                 "jargon-polished", "lay-rough", "jargon-rough"]:
        answers.append({"model": "sonnet", "qid": "aq1", "cell": cell,
                        "variant": None, "response": f"ans-{cell}", "usage": {}})

    out_seq = str(tmp_path / "judge_seq.jsonl")
    judge_all([Q], answers, FakeJudge(), out_seq, workers=1)
    out_par = str(tmp_path / "judge_par.jsonl")
    judge_all([Q], answers, FakeJudge(), out_par, workers=3)

    def key_set(path):
        return {(r["task"], r["model"], r["qid"], r["key"]) for r in read_jsonl(path)}

    seq_rows = read_jsonl(out_seq)
    par_rows = read_jsonl(out_par)
    assert len(seq_rows) == len(par_rows)
    assert key_set(out_seq) == key_set(out_par)
    assert len(key_set(out_par)) == len(par_rows)  # no duplicates

    # rerun under concurrency is still a no-op (resume works)
    judge_all([Q], answers, FakeJudge(), out_par, workers=3)
    assert len(read_jsonl(out_par)) == len(par_rows)


class ScriptedJudge:
    """FakeJudge with per-task overridable replies (valid by default)."""

    def __init__(self, coverage=None, rubric=None, pairwise=None):
        self.coverage = coverage if coverage is not None else {"c1": True, "c2": False}
        self.rubric = rubric if rubric is not None else {
            "factual_correctness": 6, "completeness": 5,
            "actionability": 6, "appropriate_caution": 7}
        self.pairwise = pairwise if pairwise is not None else {"winner": "tie"}

    def chat(self, model, messages, max_tokens=1024, **kwargs):
        text = messages[0]["content"]
        if "checklist" in text.lower():
            return json.dumps(self.coverage), {}
        if "1-7" in text:
            return json.dumps(self.rubric), {}
        return json.dumps(self.pairwise), {}


def _pair_answers():
    return [{"model": "sonnet", "qid": "aq1", "cell": c, "variant": None,
             "response": f"ans-{c}", "usage": {}} for c in ("polished", "rough")]


def test_pairwise_unswap_normalizes_winner_to_cell_a(tmp_path):
    # judge always picks the FIRST-shown answer ("A" in the prompt);
    # stored winner must name the cell, not the presentation slot
    out = str(tmp_path / "judge.jsonl")
    judge_all([Q], _pair_answers(), ScriptedJudge(pairwise={"winner": "A"}), out)
    winners = {r["order"]: r["winner"]
               for r in read_jsonl(out) if r["task"] == "pairwise"}
    assert winners == {0: "A", 1: "B"}


def test_coverage_reply_missing_id_raises(tmp_path):
    out = str(tmp_path / "judge.jsonl")
    with pytest.raises(ValueError, match="aq1"):
        judge_all([Q], [BIO_ANSWER], ScriptedJudge(coverage={"c1": True}), out)


def test_rubric_reply_out_of_range_raises(tmp_path):
    out = str(tmp_path / "judge.jsonl")
    bad = {"factual_correctness": 9, "completeness": 5,
           "actionability": 6, "appropriate_caution": 7}
    with pytest.raises(ValueError, match="aq1"):
        judge_all([Q], [BIO_ANSWER], ScriptedJudge(rubric=bad), out)


def test_rubric_reply_missing_dim_raises(tmp_path):
    out = str(tmp_path / "judge.jsonl")
    bad = {"factual_correctness": 6, "completeness": 5, "actionability": 6}
    with pytest.raises(ValueError, match="aq1"):
        judge_all([Q], [BIO_ANSWER], ScriptedJudge(rubric=bad), out)


def test_pairwise_bad_winner_raises(tmp_path):
    out = str(tmp_path / "judge.jsonl")
    with pytest.raises(ValueError, match="aq1"):
        judge_all([Q], _pair_answers(),
                  ScriptedJudge(pairwise={"winner": "Answer A"}), out)


Q2 = {**Q, "qid": "aq2"}
MIXED_ANSWERS = [
    {"model": "sonnet", "qid": "aq1", "cell": "control", "variant": None,
     "response": "sonnet ans", "usage": {}},
    {"model": "qwen", "qid": "aq1", "cell": "control", "variant": None,
     "response": "qwen ans", "usage": {}},
]


def test_restrict_judge_passthrough_when_none():
    questions, answers = restrict_judge([Q, Q2], MIXED_ANSWERS, None, None)
    assert questions == [Q, Q2]
    assert answers == MIXED_ANSWERS


def test_restrict_judge_limit_slices_questions():
    questions, answers = restrict_judge([Q, Q2], MIXED_ANSWERS, 1, None)
    assert questions == [Q]
    assert answers == MIXED_ANSWERS  # only_model not set, rows untouched


def test_restrict_judge_only_model_filters_rows():
    questions, answers = restrict_judge([Q, Q2], MIXED_ANSWERS, None, "qwen")
    assert questions == [Q, Q2]  # limit not set, questions untouched
    assert answers == [MIXED_ANSWERS[1]]
    assert all(r["model"] == "qwen" for r in answers)


def test_restrict_judge_limit_and_only_model_together():
    questions, answers = restrict_judge([Q, Q2], MIXED_ANSWERS, 1, "sonnet")
    assert questions == [Q]
    assert answers == [MIXED_ANSWERS[0]]


def test_restrict_judge_unknown_model_raises_systemexit():
    with pytest.raises(SystemExit):
        restrict_judge([Q], MIXED_ANSWERS, None, "nope")
