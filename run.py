"""Generation calls for all arms. Idempotent: reruns skip completed rows.

Usage:
  uv run python run.py --smoke      # smoke stimuli -> results/smoke/<stamp>/
  uv run python run.py              # full run      -> results/full/<stamp>/
  uv run python run.py --check-models

Each run writes mcq.jsonl + advice.jsonl into results/<kind>/<stamp>/ with a
`latest` symlink per kind. Reruns resume the latest run dir; --fresh starts
a new stamped dir.
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import yaml

from common import (MODEL_EXTRA, MODELS, ChatClient, append_jsonl,
                    done_keys, read_jsonl, run_dir)
from prompts import build_mcq_prompt, classify, parse_letter, variant_for

# control first: each model's ceiling is known before persona cells are spent
MCQ_PERSONAS = ["control", "edu-high", "edu-low", "polished", "rough"]
ADVICE_BIO_CELLS = MCQ_PERSONAS  # bio cells answer the canonical lay-polished text
ADVICE_PHRASING_CELLS = ["jargon-polished", "lay-rough", "jargon-rough"]
ADVICE_CELLS = ADVICE_BIO_CELLS + ADVICE_PHRASING_CELLS


def bio_for(persona, personas, q_index):
    if persona == "control":
        return None, None
    variants = personas[persona]["variants"]
    v = variant_for(q_index, len(variants))
    return variants[v], v


def _persistent_403(e):
    """True for a moderation/permission block that survived all retries.

    Recorded as a per-row status instead of aborting the whole run —
    it's data (like a refusal), not an infrastructure failure.
    """
    return (isinstance(e, httpx.HTTPStatusError)
            and e.response is not None and e.response.status_code == 403)


def _mcq_call(client, model, prompt):
    try:
        raw, usage = client.chat(MODELS.get(model, model),
                                 [{"role": "user", "content": prompt}],
                                 max_tokens=8, extra=MODEL_EXTRA[model])
    except httpx.HTTPStatusError as e:
        if _persistent_403(e):
            return "", {}, True
        raise
    return raw or "", usage, False  # content can be null; never store None


def _mcq_row(model, q, persona, v, prompt, raw, usage, blocked=False):
    letter = parse_letter(raw, len(q["options"]))
    correct = (letter is not None
               and ord(letter) - ord("A") == q["answer_idx"])
    return {
        "model": model, "qid": q["qid"], "cell": persona, "variant": v,
        "prompt": prompt,
        "raw": raw, "letter": letter, "correct": correct,
        "status": "blocked" if blocked else classify(raw, len(q["options"])),
        "source": q["source"], "usage": usage,
    }


def run_mcq(questions, models, personas, client, out_path, workers=1):
    done = done_keys(out_path, ["model", "qid", "cell"])
    total = len(models) * len(MCQ_PERSONAS) * len(questions)

    # Build the full ordered job list first (skipping done rows). Each job
    # carries everything needed for the call and the output row except the
    # response-dependent fields (raw/usage), which the call fills in.
    jobs = []
    for model in models:
        for persona in MCQ_PERSONAS:
            for i, q in enumerate(questions):
                if (model, q["qid"], persona) not in done:
                    bio, v = bio_for(persona, personas, i)
                    prompt = build_mcq_prompt(bio, q["question"], q["options"])
                    jobs.append((model, q, persona, v, prompt))

    n_skipped = total - len(jobs)
    n = n_skipped

    if workers == 1:
        for model, q, persona, v, prompt in jobs:
            raw, usage, blocked = _mcq_call(client, model, prompt)
            append_jsonl(out_path,
                         _mcq_row(model, q, persona, v, prompt, raw, usage, blocked))
            n += 1
            if n % 200 == 0:
                print(f"mcq {n}/{total}", file=sys.stderr)
        return

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {}
        for job in jobs:
            model, q, persona, v, prompt = job
            fut = executor.submit(_mcq_call, client, model, prompt)
            futures[fut] = job
        for fut in as_completed(futures):
            raw, usage, blocked = fut.result()  # propagates worker exceptions here
            model, q, persona, v, prompt = futures[fut]
            append_jsonl(out_path,
                         _mcq_row(model, q, persona, v, prompt, raw, usage, blocked))
            n += 1
            if n % 200 == 0:
                print(f"mcq {n}/{total}", file=sys.stderr)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def advice_prompt(q, cell, personas, q_index):
    if cell in ADVICE_BIO_CELLS:
        text = q["phrasings"]["lay-polished"]
        if cell == "control":
            return text
        bio, _ = bio_for(cell, personas, q_index)
        return bio + "\n\n" + text
    return q["phrasings"][cell]


def _advice_call(client, model, prompt):
    try:
        # 4000: a 1200 cap was found to bind differentially (hidden reasoning
        # burn on some models truncated long-answer cells) — see RESULTS notes
        response, usage = client.chat(MODELS.get(model, model),
                                      [{"role": "user", "content": prompt}],
                                      max_tokens=4000, extra=MODEL_EXTRA[model])
    except httpx.HTTPStatusError as e:
        if _persistent_403(e):
            return "", {}, True
        raise
    return response or "", usage, False


def _advice_row(model, q, cell, v, prompt, response, usage, blocked=False):
    return {"model": model, "qid": q["qid"], "cell": cell,
            "variant": v, "prompt": prompt,
            "response": response, "usage": usage, "blocked": blocked}


def run_advice(questions, models, personas, client, out_path, workers=1):
    done = done_keys(out_path, ["model", "qid", "cell"])
    total = len(models) * len(ADVICE_CELLS) * len(questions)

    # Build the full ordered job list first (skipping done rows).
    jobs = []
    for model in models:
        for cell in ADVICE_CELLS:
            for i, q in enumerate(questions):
                if (model, q["qid"], cell) not in done:
                    _, v = (bio_for(cell, personas, i) if cell in ADVICE_BIO_CELLS
                            else (None, None))
                    prompt = advice_prompt(q, cell, personas, i)
                    jobs.append((model, q, cell, v, prompt))

    n_skipped = total - len(jobs)
    n = n_skipped

    if workers == 1:
        for model, q, cell, v, prompt in jobs:
            response, usage, blocked = _advice_call(client, model, prompt)
            append_jsonl(out_path,
                         _advice_row(model, q, cell, v, prompt, response, usage, blocked))
            n += 1
            if n % 25 == 0:
                print(f"advice {n}/{total}", file=sys.stderr)
        return

    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {}
        for job in jobs:
            model, q, cell, v, prompt = job
            fut = executor.submit(_advice_call, client, model, prompt)
            futures[fut] = job
        for fut in as_completed(futures):
            response, usage, blocked = fut.result()  # propagates worker exceptions here
            model, q, cell, v, prompt = futures[fut]
            append_jsonl(out_path,
                         _advice_row(model, q, cell, v, prompt, response, usage, blocked))
            n += 1
            if n % 25 == 0:
                print(f"advice {n}/{total}", file=sys.stderr)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def restrict(questions, models, limit, only_model):
    """Apply --limit/--only-model to a questions list and the models list.

    questions: list of question lists (e.g. [mcq_questions, advice_questions])
               so both lists get sliced identically.
    Returns (questions, models). Unknown only_model -> SystemExit.
    """
    if only_model is not None:
        if only_model not in MODELS:
            raise SystemExit(f"unknown model key {only_model!r}; choices: {sorted(MODELS)}")
        models = [only_model]
    if limit is not None:
        questions = [qs[:limit] for qs in questions]
    return questions, models


def check_models(client):
    pricing = client.model_pricing()
    from common import JUDGE_MODEL
    ok = True
    for mid in list(MODELS.values()) + [JUDGE_MODEL]:
        if mid in pricing:
            p, c = pricing[mid]
            print(f"OK   {mid}  prompt=${p * 1e6:.2f}/Mtok completion=${c * 1e6:.2f}/Mtok")
        else:
            ok = False
            print(f"MISSING {mid} — update common.MODELS with the current best ID")
    if not ok:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--check-models", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="slice each question list to its first N rows")
    ap.add_argument("--only-model", choices=list(MODELS), default=None,
                    help="restrict the model list to this single key")
    ap.add_argument("--workers", type=int, default=5,
                    help="parallel API calls (1 = sequential)")
    ap.add_argument("--fresh", action="store_true",
                    help="start a new timestamped run dir instead of resuming latest")
    args = ap.parse_args()

    client = ChatClient()
    if args.check_models:
        check_models(client)
        return
    with open("personas.yaml") as f:
        personas = yaml.safe_load(f)
    models = list(MODELS)
    d = run_dir("smoke" if args.smoke else "full", fresh=args.fresh)
    if args.smoke:
        mcq_qs = read_jsonl("questions/smoke_mcq.jsonl")
        advice_qs = read_jsonl("questions/advice_smoke.jsonl")
    else:
        mcq_qs = read_jsonl("questions/mcq.jsonl")
        advice_qs = [q for q in read_jsonl("questions/advice.jsonl") if not q.get("smoke")]
    (mcq_qs, advice_qs), models = restrict([mcq_qs, advice_qs], models,
                                           args.limit, args.only_model)
    run_mcq(mcq_qs, models, personas, client, os.path.join(d, "mcq.jsonl"),
            workers=args.workers)
    run_advice(advice_qs, models, personas, client, os.path.join(d, "advice.jsonl"),
               workers=args.workers)


if __name__ == "__main__":
    main()
