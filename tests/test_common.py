import json
import os

import httpx
import pytest

from common import ChatClient, append_jsonl, done_keys, read_jsonl, run_dir


def test_jsonl_roundtrip_and_done_keys(tmp_path):
    p = tmp_path / "r.jsonl"
    append_jsonl(str(p), {"model": "m1", "qid": "q1", "cell": "control", "x": 1})
    append_jsonl(str(p), {"model": "m1", "qid": "q2", "cell": "rough", "x": 2})
    rows = read_jsonl(str(p))
    assert len(rows) == 2 and rows[1]["x"] == 2
    keys = done_keys(str(p), ["model", "qid", "cell"])
    assert ("m1", "q1", "control") in keys
    assert ("m1", "q9", "control") not in keys


def test_read_jsonl_missing_file(tmp_path):
    assert read_jsonl(str(tmp_path / "nope.jsonl")) == []


def test_read_jsonl_skips_truncated_final_line(tmp_path, capsys):
    p = tmp_path / "t.jsonl"
    p.write_text('{"a": 1}\n{"b": 2}\n{"c": ')  # mid-write crash artifact
    assert read_jsonl(str(p)) == [{"a": 1}, {"b": 2}]
    assert "truncated" in capsys.readouterr().err.lower()


def test_read_jsonl_raises_on_malformed_middle_line(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"a": 1}\nnot json\n{"c": 3}\n')  # real corruption, not truncation
    try:
        read_jsonl(str(p))
        assert False, "expected JSONDecodeError"
    except json.JSONDecodeError:
        pass


def make_client(handler):
    return ChatClient(api_key="test-key", transport=httpx.MockTransport(handler))


def test_chat_returns_content_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["model"] == "some/model"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": " (B)"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        })

    content, usage = make_client(handler).chat("some/model", [{"role": "user", "content": "hi"}])
    assert content == " (B)"
    assert usage["prompt_tokens"] == 10


def test_chat_retries_on_429(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "A"}}], "usage": {}})

    content, _ = make_client(handler).chat("m", [{"role": "user", "content": "x"}])
    assert content == "A" and calls["n"] == 3


def test_chat_fails_fast_on_401(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"error": "bad key"})

    try:
        make_client(handler).chat("m", [{"role": "user", "content": "x"}])
        assert False, "expected HTTPStatusError"
    except httpx.HTTPStatusError:
        pass
    assert calls["n"] == 1


def test_run_dir_creates_stamped_dir_and_latest_symlink(tmp_path):
    root = str(tmp_path / "results")
    d = run_dir("smoke", root=root)
    assert os.path.isdir(d)
    assert os.path.basename(d) != "latest"  # real stamped path, not the symlink
    latest = os.path.join(root, "smoke", "latest")
    assert os.path.islink(latest)
    assert os.readlink(latest) == os.path.basename(d)  # relative target


def test_run_dir_default_resumes_same_dir(tmp_path):
    root = str(tmp_path / "results")
    d1 = run_dir("smoke", root=root)
    d2 = run_dir("smoke", root=root)
    assert d1 == d2  # resume semantics: no fresh flag -> same run dir


def test_run_dir_fresh_creates_new_dir_and_repoints_latest(tmp_path):
    root = str(tmp_path / "results")
    d1 = run_dir("full", root=root)
    d2 = run_dir("full", fresh=True, root=root)  # same second -> dedup suffix
    assert d1 != d2
    assert os.path.isdir(d1) and os.path.isdir(d2)  # old run untouched
    latest = os.path.join(root, "full", "latest")
    assert os.readlink(latest) == os.path.basename(d2)
    assert run_dir("full", root=root) == d2  # resume now follows the new dir


def test_run_dir_create_false_requires_existing_run(tmp_path):
    root = str(tmp_path / "results")
    with pytest.raises(SystemExit, match="smoke"):
        run_dir("smoke", create=False, root=root)
    d = run_dir("smoke", root=root)
    assert run_dir("smoke", create=False, root=root) == d


def test_chat_retries_200_without_choices(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(200, json={"error": {"message": "provider hiccup"}})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "A"}}], "usage": {}})

    content, _ = make_client(handler).chat("m", [{"role": "user", "content": "x"}])
    assert content == "A" and calls["n"] == 3


def test_chat_raises_on_persistent_choiceless_200(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def handler(request):
        return httpx.Response(200, json={"error": {"message": "still broken"}})

    try:
        make_client(handler).chat("m", [{"role": "user", "content": "x"}])
        assert False, "expected TransportError"
    except httpx.TransportError as e:
        assert "without choices" in str(e)
