import pytest

from build_mcq import filter_hard, sample_indices, shuffle_options
from common import append_jsonl, read_jsonl


def test_shuffle_deterministic_and_tracks_answer():
    opts = ["w1", "w2", "correct", "w3"]
    a, ai = shuffle_options(opts, 2, seed=7, qid="tqa-1")
    b, bi = shuffle_options(opts, 2, seed=7, qid="tqa-1")
    assert a == b and ai == bi
    assert a[ai] == "correct"
    assert sorted(a) == sorted(opts)


def test_shuffle_varies_by_qid():
    opts = [str(i) for i in range(8)]
    a, _ = shuffle_options(opts, 0, seed=7, qid="q1")
    b, _ = shuffle_options(opts, 0, seed=7, qid="q2")
    assert a != b  # 8! permutations; collision ~ never


def test_sample_indices_deterministic_disjoint_smoke():
    main, smoke = sample_indices(n_total=817, n_main=400, n_smoke=5, seed=13)
    main2, smoke2 = sample_indices(n_total=817, n_main=400, n_smoke=5, seed=13)
    assert main == main2 and smoke == smoke2
    assert len(main) == 400 and len(smoke) == 5
    assert not set(main) & set(smoke)


class FakeClient:
    """Canned-response stand-in for ChatClient; no HTTP."""

    def __init__(self, responses):
        self.responses = list(responses)  # consumed in call order
        self.calls = []  # prompt content of each chat() call

    def chat(self, model, messages, max_tokens=1024):
        self.calls.append(messages[0]["content"])
        return self.responses.pop(0), {}


def make_item(qid, question="Q?", options=("right", "wrong"), answer_idx=0):
    return {"qid": qid, "source": "t", "question": question,
            "options": list(options), "answer_idx": answer_idx}


def test_filter_hard_uses_cache(tmp_path):
    cache = str(tmp_path / "cache.jsonl")
    append_jsonl(cache, {"qid": "q1", "raw": "B"})  # wrong (answer is A) -> hard
    client = FakeClient(["B"])  # only q2 should reach the client
    items = [make_item("q1"), make_item("q2", question="Only q2 hits the client")]
    hard = filter_hard(items, client, n_keep=2, cache_path=cache)
    assert [i["qid"] for i in hard] == ["q1", "q2"]
    assert len(client.calls) == 1
    assert "Only q2 hits the client" in client.calls[0]
    assert {r["qid"] for r in read_jsonl(cache)} == {"q1", "q2"}  # q2 now cached


def test_filter_hard_exhaustion_raises_actionable(tmp_path):
    client = FakeClient(["A", "A"])  # both correct -> zero hard items
    items = [make_item("q1"), make_item("q2")]
    with pytest.raises(SystemExit) as exc:
        filter_hard(items, client, n_keep=1, cache_path=str(tmp_path / "c.jsonl"))
    msg = str(exc.value)
    assert "only 0 hard items found (need 1)" in msg
    assert "increase" in msg and "filter cache" in msg


def test_filter_hard_skips_parse_failures(tmp_path):
    client = FakeClient(["I think...", "B"])  # q1 unparseable, q2 wrong
    items = [make_item("q1"), make_item("q2")]
    hard = filter_hard(items, client, n_keep=1, cache_path=str(tmp_path / "c.jsonl"))
    assert [i["qid"] for i in hard] == ["q2"]  # q1 counted neither right nor wrong
    assert len(client.calls) == 2  # q1 was still queried (and cached), just not kept
