"""Second-judge rescore of ALL advice judging (instrument audit).

Judge 2 = moonshotai/kimi-k2.6 (Moonshot lineage — disjoint from all four
evaluated models AND from the primary gemini judge). Replicates all three
instruments — coverage, rubric, order-balanced pairwise — with the same
prompts and validation as judge.py. Writes judge2.jsonl beside judge.jsonl.
Resume-idempotent on (task, model, qid, key).

Usage: uv run python rescore.py
"""
import os
import sys

from common import ChatClient, append_jsonl, read_jsonl, run_dir
from judge import (PAIRS, _validate_coverage, _validate_rubric, coverage_prompt,
                   pairwise_prompt, parse_json_reply, rubric_prompt)

JUDGE2 = "moonshotai/kimi-k2.6"
JUDGE2_EXTRA = {"reasoning": {"enabled": False},
                "provider": {"order": ["CoreWeave"], "allow_fallbacks": False}}
CELLS = ("control", "edu-high", "edu-low", "polished", "rough",
         "jargon-polished", "lay-rough", "jargon-rough")


def main():
    d = run_dir("full", create=False)
    questions = {q["qid"]: q for q in read_jsonl("questions/advice.jsonl")
                 if not q.get("smoke")}
    rows = [r for r in read_jsonl(os.path.join(d, "advice.jsonl"))
            if r["cell"] in CELLS and not r.get("blocked")]
    by_key = {(r["model"], r["qid"], r["cell"]): r for r in rows}
    out = os.path.join(d, "judge2.jsonl")
    # early rows were written without a "key" field; fall back to cell
    done = {(r.get("task", "coverage"), r["model"], r["qid"], r.get("key", r.get("cell")))
            for r in read_jsonl(out)}
    client = ChatClient()
    total = len(rows) * 2 + len(PAIRS) * len(questions) * 4 * 2
    n = 0

    def call(prompt):
        raw, _ = client.chat(JUDGE2, [{"role": "user", "content": prompt}],
                             max_tokens=400, extra=JUDGE2_EXTRA)
        return parse_json_reply(raw), raw

    for task, builder in [("coverage", coverage_prompt), ("rubric", rubric_prompt)]:
        for r in rows:
            n += 1
            key = r["cell"]
            if (task, r["model"], r["qid"], key) not in done:
                q = questions[r["qid"]]
                prompt = builder(q, r)
                reply, raw = call(prompt)
                if task == "coverage":
                    field, reply = "items", _validate_coverage(reply, q, r["qid"])
                else:
                    field, reply = "scores", _validate_rubric(reply, r["qid"])
                append_jsonl(out, {"task": task, "judge": JUDGE2, "model": r["model"],
                                   "qid": r["qid"], "cell": r["cell"], "key": key,
                                   field: reply, "prompt": prompt, "raw": raw})
            if n % 40 == 0:
                print(f"rescore {n}/{total}", file=sys.stderr)

    models = sorted({r["model"] for r in rows})
    for label, cell_a, cell_b in PAIRS:
        for qid, q in questions.items():
            for m in models:
                ra = by_key.get((m, qid, cell_a))
                rb = by_key.get((m, qid, cell_b))
                for order in (0, 1):
                    n += 1
                    key = f"{label}:{order}"
                    if ra and rb and ("pairwise", m, qid, key) not in done:
                        prompt = pairwise_prompt(q, ra["response"], rb["response"], order)
                        reply, raw = call(prompt)
                        winner = reply.get("winner", "tie")
                        if winner not in ("A", "B", "tie"):
                            raise ValueError(f"pairwise reply for {qid}: bad winner "
                                             f"{winner!r}: {reply}")
                        if order == 1 and winner in ("A", "B"):
                            winner = "B" if winner == "A" else "A"  # A = cell_a always
                        append_jsonl(out, {"task": "pairwise", "judge": JUDGE2, "model": m,
                                           "qid": qid, "key": key, "pair": [cell_a, cell_b],
                                           "order": order, "winner": winner,
                                           "prompt": prompt, "raw": raw})
                    if n % 40 == 0:
                        print(f"rescore {n}/{total}", file=sys.stderr)
    print(f"judge2 complete -> {out}")


if __name__ == "__main__":
    main()
