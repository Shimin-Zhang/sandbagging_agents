import json
import os
import sys
import time
from datetime import datetime

import httpx

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
LOCAL_BASE = "http://localhost:8090/v1"  # llama-server (make filter-server)

# Lineup priced from /models on 2026-08-14 (see spec Models section);
# re-verify with run.py --check-models before the smoke round. Date-pinned
# snapshots over "-latest" aliases: aliases get silently upgraded mid-run.
MODELS = {
    "sonnet": "anthropic/claude-sonnet-5",
    "luna": "openai/gpt-5.6-luna-pro",
    "dsflash": "deepseek/deepseek-v4-flash-0731",
    "qwen": "qwen/qwen3-235b-a22b-2507",
}
JUDGE_MODEL = "google/gemini-3.7-flash"

# Provider pinning: OpenRouter routes per-call across hosts of varying
# quality (smoke caught DeepInfra's qwen emitting token salad at temp 0).
# Pin each model to probed-clean providers, no fallbacks — deterministic
# hosts, and outages fail loud + resume. Reasoning disabled everywhere
# (the judge's host mandates reasoning; effort=low keeps it ~60 tok).
NO_REASONING = {"reasoning": {"enabled": False}}
MODEL_EXTRA = {
    "sonnet": {**NO_REASONING,
               "provider": {"order": ["Anthropic"], "allow_fallbacks": False}},
    "luna": {**NO_REASONING,
             "provider": {"order": ["OpenAI"], "allow_fallbacks": False}},
    "dsflash": {**NO_REASONING,
                "provider": {"order": ["Baidu", "DigitalOcean"],
                             "allow_fallbacks": False}},
    "qwen": {**NO_REASONING,
             "provider": {"order": ["Alibaba"], "allow_fallbacks": False}},
}
JUDGE_EXTRA = {"reasoning": {"effort": "low"},
               "provider": {"order": ["Google AI Studio"],
                            "allow_fallbacks": False}}

# 403 included: OpenRouter uses it for moderation/abuse-heuristic blocks,
# which are often transient (a mid-run 403 replayed clean). Genuinely bad
# credentials surface as 401, which still fails fast.
RETRYABLE_STATUSES = (403, 429, 500, 502, 503, 529)


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        lines = [line for line in f if line.strip()]
    rows = []
    for i, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:  # mid-write crash leaves a truncated tail; safe to drop
                print(f"warning: skipping truncated final line in {path}", file=sys.stderr)
                break
            raise  # malformed non-final line = real corruption, not truncation
    return rows


def append_jsonl(path, row):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def done_keys(path, key_fields):
    return {tuple(r[k] for k in key_fields) for r in read_jsonl(path)}


def run_dir(kind, fresh=False, create=True, root="results"):
    """Resolve the active run directory for kind ('smoke'|'full').

    Default: reuse results/<kind>/latest. With fresh=True (or no latest),
    create results/<kind>/<YYYYMMDD-HHMMSS>/ (dedup suffix -2, -3... on
    collision) and repoint the latest symlink. create=False: never create;
    SystemExit with a clear message if no run exists (for analyze/judge).
    Returns the REAL stamped path (not the symlink), printed to stderr.
    """
    kind_root = os.path.join(root, kind)
    latest = os.path.join(kind_root, "latest")
    if not fresh and os.path.islink(latest):
        d = os.path.join(kind_root, os.readlink(latest))
        print(f"run dir: {d}", file=sys.stderr)
        return d
    if not create:
        raise SystemExit(f"no {kind} run found under {kind_root} — "
                         "run run.py first (it creates the run dir)")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    d = os.path.join(kind_root, stamp)
    suffix = 2
    while os.path.exists(d):  # same-second fresh calls: dedup -2, -3, ...
        d = os.path.join(kind_root, f"{stamp}-{suffix}")
        suffix += 1
    os.makedirs(d)
    if os.path.islink(latest):
        os.remove(latest)
    os.symlink(os.path.basename(d), latest)  # relative target = the stamp name
    print(f"run dir: {d}", file=sys.stderr)
    return d


class ChatClient:
    def __init__(self, base_url=OPENROUTER_BASE, api_key=None, transport=None):
        self.base_url = base_url
        headers = {}
        key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self.http = httpx.Client(headers=headers, timeout=180, transport=transport)

    def chat(self, model, messages, max_tokens=1024, retries=5, extra=None):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        if extra:
            payload.update(extra)
        for attempt in range(retries):
            try:
                r = self.http.post(f"{self.base_url}/chat/completions", json=payload)
                if r.status_code in RETRYABLE_STATUSES:
                    raise httpx.HTTPStatusError(
                        f"retryable {r.status_code}: {r.text[:200]}",
                        request=r.request, response=r)
                if r.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        f"HTTP {r.status_code}: {r.text[:300]}",
                        request=r.request, response=r)
                data = r.json()
                if "choices" not in data:
                    # OpenRouter can return 200 with an embedded error object
                    # (transient provider failure) — retry via TransportError
                    err = json.dumps(data.get("error", data))[:300]
                    raise httpx.TransportError(f"200 without choices: {err}")
                return data["choices"][0]["message"]["content"], data.get("usage", {}) or {}
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                if (
                    isinstance(e, httpx.HTTPStatusError)
                    and e.response.status_code not in RETRYABLE_STATUSES
                ):
                    raise  # 401/400/404 etc.: fail fast, retrying won't help
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)

    def model_pricing(self):
        """{model_id: (usd_per_prompt_token, usd_per_completion_token)} from /models."""
        r = self.http.get(f"{self.base_url}/models")
        r.raise_for_status()
        out = {}
        for m in r.json()["data"]:
            p = m.get("pricing", {})
            out[m["id"]] = (float(p.get("prompt", 0)), float(p.get("completion", 0)))
        return out
