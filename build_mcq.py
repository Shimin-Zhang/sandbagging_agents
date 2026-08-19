"""Build the frozen MCQ question sets.

Usage: make filter-server (separate terminal), then: make questions
Emits questions/mcq.jsonl (800 items) + questions/smoke_mcq.jsonl (5 TQA items).
Filter calls are cached in questions/filter_cache.jsonl (resumable).
"""
import random

from common import LOCAL_BASE, ChatClient, append_jsonl, done_keys, read_jsonl
from prompts import build_mcq_prompt, parse_letter

SEED = 20260814


def shuffle_options(options, answer_idx, seed, qid):
    rng = random.Random(f"{seed}:{qid}")
    order = list(range(len(options)))
    rng.shuffle(order)
    return [options[i] for i in order], order.index(answer_idx)


def sample_indices(n_total, n_main, n_smoke, seed):
    rng = random.Random(seed)
    picked = rng.sample(range(n_total), n_main + n_smoke)
    return picked[:n_main], picked[n_main:]


def filter_hard(candidates, client, n_keep=200, cache_path="questions/filter_cache.jsonl"):
    """Return first n_keep candidates the local filter model answers incorrectly.

    'Wrong' = a parsed letter that differs from the answer. Parse failures are
    skipped (they signal formatting trouble, not difficulty).
    """
    cached = {r["qid"]: r for r in read_jsonl(cache_path)}
    hard = []
    for item in candidates:
        if len(hard) >= n_keep:
            break
        row = cached.get(item["qid"])
        if row is None:
            raw, _ = client.chat("local", [{"role": "user", "content":
                build_mcq_prompt(None, item["question"], item["options"])}], max_tokens=8)
            row = {"qid": item["qid"], "raw": raw}
            append_jsonl(cache_path, row)
        letter = parse_letter(row["raw"], len(item["options"]))
        if letter is None:
            continue
        if ord(letter) - ord("A") != item["answer_idx"]:
            hard.append(item)
    if len(hard) < n_keep:
        raise SystemExit(
            f"only {len(hard)} hard items found (need {n_keep}); increase the "
            "1000-candidate sample size in main() and rerun — the filter cache "
            "reuses existing verdicts"
        )
    return hard


def load_sources():
    from datasets import load_dataset

    tqa = load_dataset("truthfulqa/truthful_qa", "multiple_choice",
                       revision="741b8276f2d1982aa3d5b832d3ee81ed3b896490")["validation"]  # pinned 2026-08-14
    tqa_items = []
    for i, row in enumerate(tqa):
        choices = row["mc1_targets"]["choices"]
        tqa_items.append({"qid": f"tqa-{i:04d}", "source": "truthfulqa",
                          "question": row["question"], "options": choices,
                          "answer_idx": row["mc1_targets"]["labels"].index(1)})

    mmlu = load_dataset("cais/mmlu", "all",
                        revision="c30699e8356da336a370243923dbaf21066bb9fe")["test"]  # pinned 2026-08-14
    mmlu_items = [{"qid": f"mmlu-{i:05d}", "source": "mmlu", "question": r["question"],
                   "options": r["choices"], "answer_idx": r["answer"]}
                  for i, r in enumerate(mmlu)]

    pro = load_dataset("TIGER-Lab/MMLU-Pro",
                       revision="b189ec765aa7ed75c8acfea42df31fdae71f97be")["test"]  # pinned 2026-08-14
    pro_items = [{"qid": f"mmlupro-{i:05d}", "source": "mmlupro", "question": r["question"],
                  "options": r["options"], "answer_idx": r["answer_index"]}
                 for i, r in enumerate(pro)]
    return tqa_items, mmlu_items, pro_items


def pick(items, indices):
    return [items[i] for i in indices]


def main():
    tqa_items, mmlu_items, pro_items = load_sources()
    main_idx, smoke_idx = sample_indices(len(tqa_items), 400, 5, SEED)
    client = ChatClient(base_url=LOCAL_BASE, api_key="")

    # 2000: the filter model answered 84% of the first 1000 MMLU candidates
    # correctly, yielding only 159 hard items — MMLU-Pro at 1000 is plenty
    mmlu_cand = pick(mmlu_items, random.Random(SEED + 1).sample(range(len(mmlu_items)), 2000))
    pro_cand = pick(pro_items, random.Random(SEED + 2).sample(range(len(pro_items)), 1000))
    final = (pick(tqa_items, main_idx)
             + filter_hard(mmlu_cand, client)
             + filter_hard(pro_cand, client))

    for path, items in [("questions/mcq.jsonl", final),
                        ("questions/smoke_mcq.jsonl", pick(tqa_items, smoke_idx))]:
        existing = done_keys(path, ["qid"])
        for item in items:
            if (item["qid"],) in existing:
                continue
            opts, ai = shuffle_options(item["options"], item["answer_idx"], SEED, item["qid"])
            append_jsonl(path, {**item, "options": opts, "answer_idx": ai})
    print(f"wrote {len(final)} main + {len(smoke_idx)} smoke questions")


if __name__ == "__main__":
    main()
