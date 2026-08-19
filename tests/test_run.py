import httpx
import threading

import pytest
import yaml

from common import read_jsonl
from run import (ADVICE_CELLS, MCQ_PERSONAS, advice_prompt, restrict, run_advice,
                 run_mcq)


class FakeClient:
    def __init__(self, reply="A"):
        self.reply = reply
        self.calls = []
        self.extras = []

    def chat(self, model, messages, max_tokens=1024, extra=None):
        self.calls.append((model, messages[0]["content"]))
        self.extras.append(extra)
        return self.reply, {"prompt_tokens": 1, "completion_tokens": 1}


class FailOnNthClient:
    """Raises on the Nth call (1-indexed); succeeds otherwise. Thread-safe
    call counting via a lock, since workers>1 calls chat() concurrently."""

    def __init__(self, fail_on, reply="A"):
        self.fail_on = fail_on
        self.reply = reply
        self._lock = threading.Lock()
        self._count = 0

    def chat(self, model, messages, max_tokens=1024, extra=None):
        with self._lock:
            self._count += 1
            n = self._count
        if n == self.fail_on:
            raise RuntimeError(f"simulated failure on call {n}")
        return self.reply, {"prompt_tokens": 1, "completion_tokens": 1}


def personas():
    with open("personas.yaml") as f:
        return yaml.safe_load(f)


QUESTIONS = [
    {"qid": "q1", "source": "truthfulqa", "question": "Q one?",
     "options": ["a", "b"], "answer_idx": 0},
    {"qid": "q2", "source": "mmlu", "question": "Q two?",
     "options": ["a", "b", "c"], "answer_idx": 2},
]

ADVICE = [{"qid": "aq1", "domain": "health", "smoke": True,
           "phrasings": {"lay-polished": "PLAIN TEXT", "jargon-polished": "JARGON TEXT",
                          "lay-rough": "plain rough", "jargon-rough": "jargon rough"},
           "substitutions": [["x", "y"]],
           "checklist": [{"id": "c1", "tag": "fact", "text": "t"}]}]


def test_mcq_control_first_and_full_coverage(tmp_path):
    out = str(tmp_path / "mcq.jsonl")
    client = FakeClient()
    run_mcq(QUESTIONS, ["sonnet", "qwen"], personas(), client, out)
    rows = read_jsonl(out)
    assert len(rows) == len(QUESTIONS) * len(MCQ_PERSONAS) * 2
    # every generation call must disable extended thinking + pin providers
    assert all(x["reasoning"] == {"enabled": False} and "provider" in x
               for x in client.extras)
    per_model = [r["cell"] for r in rows if r["model"] == "sonnet"]
    n_ctrl = len(QUESTIONS)
    assert all(c == "control" for c in per_model[:n_ctrl])
    assert rows[0]["correct"] is True and rows[0]["status"] == "ok"
    assert all(r.get("prompt") for r in rows)
    control_row = next(r for r in rows if r["model"] == "sonnet" and r["cell"] == "control"
                        and r["qid"] == "q1")
    assert control_row["prompt"].startswith("Question:")
    edu_low_row = next(r for r in rows if r["model"] == "sonnet" and r["cell"] == "edu-low"
                        and r["qid"] == "q1")
    assert "Danny" in edu_low_row["prompt"]


def test_mcq_resume_skips_done(tmp_path):
    out = str(tmp_path / "mcq.jsonl")
    c1 = FakeClient()
    run_mcq(QUESTIONS, ["sonnet"], personas(), c1, out)
    c2 = FakeClient()
    run_mcq(QUESTIONS, ["sonnet"], personas(), c2, out)
    assert c2.calls == []
    assert len(read_jsonl(out)) == len(QUESTIONS) * len(MCQ_PERSONAS)


def test_mcq_workers3_full_coverage_no_duplicates(tmp_path):
    out = str(tmp_path / "mcq.jsonl")
    client = FakeClient()
    run_mcq(QUESTIONS, ["sonnet", "qwen"], personas(), client, out, workers=3)
    rows = read_jsonl(out)
    assert len(rows) == len(QUESTIONS) * len(MCQ_PERSONAS) * 2
    keys = [(r["model"], r["qid"], r["cell"]) for r in rows]
    expected = {(m, q["qid"], p) for m in ["sonnet", "qwen"]
                for p in MCQ_PERSONAS for q in QUESTIONS}
    assert set(keys) == expected
    assert len(keys) == len(set(keys))  # no duplicate rows
    # rerun is a no-op (resume still works under concurrency)
    c2 = FakeClient()
    run_mcq(QUESTIONS, ["sonnet", "qwen"], personas(), c2, out, workers=3)
    assert c2.calls == []
    assert len(read_jsonl(out)) == len(rows)


def test_mcq_workers3_worker_exception_propagates_no_corruption(tmp_path):
    out = str(tmp_path / "mcq.jsonl")
    client = FailOnNthClient(fail_on=3)
    with pytest.raises(RuntimeError, match="simulated failure"):
        run_mcq(QUESTIONS, ["sonnet", "qwen"], personas(), client, out, workers=3)
    # every row that did get written must be valid, complete JSON
    rows = read_jsonl(out)  # raises/warns on corruption; here it must succeed cleanly
    for r in rows:
        assert set(r) >= {"model", "qid", "cell", "raw", "letter", "correct"}


def test_advice_cells_and_prompts(tmp_path):
    out = str(tmp_path / "advice.jsonl")
    client = FakeClient(reply="some advice")
    run_advice(ADVICE, ["sonnet"], personas(), client, out)
    rows = read_jsonl(out)
    assert len(rows) == len(ADVICE_CELLS)  # 8 cells x 1 q x 1 model
    cells = {r["cell"] for r in rows}
    assert cells == set(ADVICE_CELLS)
    assert all(r.get("prompt") for r in rows)
    jargon_rough_row = next(r for r in rows if r["cell"] == "jargon-rough")
    assert jargon_rough_row["prompt"] == ADVICE[0]["phrasings"]["jargon-rough"]


def test_advice_prompt_composition():
    p = personas()
    q = ADVICE[0]
    assert advice_prompt(q, "control", p, 0) == "PLAIN TEXT"
    bio = advice_prompt(q, "edu-low", p, 0)
    assert bio.endswith("PLAIN TEXT") and "Danny" in bio
    assert advice_prompt(q, "jargon-rough", p, 0) == "jargon rough"
    # phrasing cells never get a biography
    assert "Danny" not in advice_prompt(q, "jargon-polished", p, 0)


def test_restrict_passthrough_when_none():
    qs, models = restrict([QUESTIONS, ADVICE], ["sonnet", "qwen"], None, None)
    assert qs == [QUESTIONS, ADVICE]
    assert models == ["sonnet", "qwen"]


def test_restrict_limit_slices_each_question_list():
    qs, models = restrict([QUESTIONS, ADVICE], ["sonnet", "qwen"], 1, None)
    assert qs == [QUESTIONS[:1], ADVICE[:1]]
    assert models == ["sonnet", "qwen"]  # models untouched by limit


def test_restrict_only_model_filters_to_single_key():
    qs, models = restrict([QUESTIONS, ADVICE], ["sonnet", "qwen"], None, "qwen")
    assert models == ["qwen"]
    assert qs == [QUESTIONS, ADVICE]  # questions untouched by only_model


def test_restrict_limit_and_only_model_together():
    qs, models = restrict([QUESTIONS], ["sonnet", "qwen"], 1, "qwen")
    assert models == ["qwen"]
    assert qs == [QUESTIONS[:1]]


def test_restrict_unknown_model_raises_systemexit():
    with pytest.raises(SystemExit):
        restrict([QUESTIONS], ["sonnet", "qwen"], None, "nope")


class Persistent403Client:
    """403 on one specific question; normal replies otherwise."""

    def __init__(self, blocked_qid):
        self.blocked_qid = blocked_qid

    def chat(self, model, messages, max_tokens=1024, extra=None):
        if f"Question: Q one?" in messages[0]["content"] and self.blocked_qid == "q1":
            req = httpx.Request("POST", "https://x")
            resp = httpx.Response(403, request=req, text='{"error":"flagged"}')
            raise httpx.HTTPStatusError("HTTP 403", request=req, response=resp)
        return "A", {"prompt_tokens": 1, "completion_tokens": 1}


def test_mcq_persistent_403_recorded_as_blocked_not_fatal(tmp_path):
    out = str(tmp_path / "mcq.jsonl")
    run_mcq(QUESTIONS, ["sonnet"], personas(), Persistent403Client("q1"), out)
    rows = read_jsonl(out)
    assert len(rows) == len(QUESTIONS) * len(MCQ_PERSONAS)  # run completed
    blocked = [r for r in rows if r["status"] == "blocked"]
    assert {r["qid"] for r in blocked} == {"q1"}
    assert all(r["raw"] == "" and r["correct"] is False for r in blocked)
    ok = [r for r in rows if r["qid"] == "q2"]
    assert all(r["status"] == "ok" for r in ok)
