"""Gaps, CIs, flip rates, coverage, charts, RESULTS.md.

--smoke: prints sanity tables + cost extrapolation, writes nothing permanent.
"""
import argparse
import os
import random
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import textstat

from common import MODELS, ChatClient, read_jsonl, run_dir

N_BOOT = 10_000


def ok_rows(rows, model, cell, source=None):
    return [r for r in rows if r["model"] == model and r["cell"] == cell
            and r["status"] == "ok" and (source is None or r["source"] == source)]


def accuracy(rows, model, cell, source=None):
    sel = ok_rows(rows, model, cell, source)
    return sum(r["correct"] for r in sel) / len(sel) if sel else float("nan")


def paired_deltas(rows, model, cell_a, cell_b, source=None):
    a = {r["qid"]: r["correct"] for r in ok_rows(rows, model, cell_a, source)}
    b = {r["qid"]: r["correct"] for r in ok_rows(rows, model, cell_b, source)}
    return [int(a[q]) - int(b[q]) for q in sorted(set(a) & set(b))]


def bootstrap_ci(deltas, n_boot=N_BOOT, seed=0):
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(n_boot))
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def flip_rate(rows, model, cell, source=None):
    ctrl = {r["qid"] for r in ok_rows(rows, model, "control", source) if r["correct"]}
    persona = {r["qid"]: r["correct"] for r in ok_rows(rows, model, cell, source)}
    flippable = [q for q in ctrl if q in persona]
    if not flippable:
        return float("nan")
    return sum(not persona[q] for q in flippable) / len(flippable)


def status_table(rows):
    counts = defaultdict(int)
    for r in rows:
        counts[(r["model"], r["cell"], r["status"])] += 1
    return dict(counts)


def coverage_by_cell(judge_rows, model):
    per_cell = defaultdict(list)
    for r in judge_rows:
        if r["task"] == "coverage" and r["model"] == model:
            vals = list(r["items"].values())
            per_cell[r["cell"]].append(sum(bool(v) for v in vals) / len(vals))
    return {c: sum(v) / len(v) for c, v in per_cell.items()}


def coverage_deltas(judge_rows, model, cell_a, cell_b, questions=None, tag=None):
    """Per-qid coverage delta; optionally restrict checklist items to one tag."""
    tags = {}
    if tag and questions:
        for q in questions:
            for c in q["checklist"]:
                tags[(q["qid"], c["id"])] = c["tag"]

    def frac(row):
        items = row["items"]
        keys = [k for k in items if not tag or tags.get((row["qid"], k)) == tag]
        return sum(bool(items[k]) for k in keys) / len(keys) if keys else None

    a, b = {}, {}
    for r in judge_rows:
        if r["task"] != "coverage" or r["model"] != model:
            continue
        f = frac(r)
        if f is None:
            continue
        if r["cell"] == cell_a:
            a[r["qid"]] = f
        elif r["cell"] == cell_b:
            b[r["qid"]] = f
    return [a[q] - b[q] for q in sorted(set(a) & set(b))]


def pairwise_scores(judge_rows):
    """Per (contrast, model): mean per-qid net score in [-1,1] + bootstrap CI.

    winner is already normalized so "A" = cell_a regardless of presentation
    order; each qid has two order-balanced judgments scored +1/0/-1 and
    averaged, then bootstrapped over qids.
    """
    per = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    by_qid = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in judge_rows:
        if r["task"] != "pairwise":
            continue
        label = r["key"].rsplit(":", 1)[0]
        s = {"A": 1, "tie": 0, "B": -1}[r["winner"]]
        by_qid[label][r["model"]][r["qid"]].append(s)
        counts[label][r["model"]][{"A": 0, "tie": 1, "B": 2}[r["winner"]]] += 1
    out = {}
    for label, models in by_qid.items():
        out[label] = {}
        for m, qids in models.items():
            deltas = [sum(v) / len(v) for v in qids.values()]
            lo, hi = bootstrap_ci(deltas, n_boot=10_000)
            w, t, l = counts[label][m]
            out[label][m] = (sum(deltas) / len(deltas), lo, hi, w, t, l)
    return out


def first_shown_rate(judge_rows):
    """Fraction of decisive pairwise judgments won by the first-shown answer."""
    first = total = 0
    for r in judge_rows:
        if r["task"] != "pairwise" or r["winner"] == "tie":
            continue
        total += 1
        if (r["order"] == 0) == (r["winner"] == "A"):
            first += 1
    return first / total if total else float("nan")


def rubric_by_cell(judge_rows, model):
    per = defaultdict(list)
    for r in judge_rows:
        if r["task"] == "rubric" and r["model"] == model:
            per[r["cell"]].append(sum(r["scores"].values()) / len(r["scores"]))
    return {c: round(sum(v) / len(v), 2) for c, v in sorted(per.items())}


def register_descriptives(advice_rows, model):
    words, fk = defaultdict(list), defaultdict(list)
    for r in advice_rows:
        if r["model"] != model:
            continue
        words[r["cell"]].append(len(r["response"].split()))
        fk[r["cell"]].append(textstat.flesch_kincaid_grade(r["response"]))
    return {c: {"mean_words": round(sum(words[c]) / len(words[c]), 1),
                "fk_grade": round(sum(fk[c]) / len(fk[c]), 1)}
            for c in words}


def require(deltas, what):
    if not deltas:
        raise SystemExit(f"no paired rows for {what} — is the run complete?")
    return deltas


def gap_chart(gaps, title, path):
    """gaps: {model: (gap, lo, hi)}"""
    fig, ax = plt.subplots(figsize=(5, 3.2))
    ms = list(gaps)
    vals = [gaps[m][0] for m in ms]
    lo_err = [gaps[m][0] - gaps[m][1] for m in ms]
    hi_err = [gaps[m][2] - gaps[m][0] for m in ms]
    ax.bar(ms, vals, yerr=[lo_err, hi_err], capsize=4, color="#4477aa")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title(title)
    ax.set_ylabel("gap")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


ARM_CONTRASTS = [  # (arm, chart title, cell_a, cell_b, mcq source)
    ("arm1", "Arm 1: acc(edu-high) - acc(edu-low), TruthfulQA", "edu-high", "edu-low", "truthfulqa"),
    ("arm2", "Arm 2: acc(polished) - acc(rough), TruthfulQA", "polished", "rough", "truthfulqa"),
]


def analyze_full():
    os.makedirs("figures", exist_ok=True)
    d = run_dir("full", create=False)
    mcq = read_jsonl(os.path.join(d, "mcq.jsonl"))
    advice = read_jsonl(os.path.join(d, "advice.jsonl"))
    judge = read_jsonl(os.path.join(d, "judge.jsonl"))
    questions = [q for q in read_jsonl("questions/advice.jsonl") if not q.get("smoke")]
    lines = ["# persona_gap results\n"]

    for arm, title, ca, cb, src in ARM_CONTRASTS:
        gaps = {}
        lines.append(f"\n## {title}\n")
        for m in MODELS:
            deltas = require(paired_deltas(mcq, m, ca, cb, src),
                             f"{arm} {ca}/{cb} model={m} source={src}")
            gap = sum(deltas) / len(deltas)
            lo, hi = bootstrap_ci(deltas)
            gaps[m] = (gap, lo, hi)
            fa, fb = flip_rate(mcq, m, ca, src), flip_rate(mcq, m, cb, src)
            bad = {c: sum(1 for r in mcq if r["model"] == m and r["cell"] == c
                          and r["source"] == src and r["status"] != "ok")
                   for c in (ca, cb)}
            lines.append(f"- {m}: gap={gap:+.3f} [{lo:+.3f}, {hi:+.3f}], "
                         f"flip_rate({ca})={fa:.3f}, flip_rate({cb})={fb:.3f}, "
                         f"n={len(deltas)}, "
                         f"refusal+parse_fail: {ca}={bad[ca]}, {cb}={bad[cb]}")
            for other_src in ["mmlu", "mmlupro"]:
                d = require(paired_deltas(mcq, m, ca, cb, other_src),
                            f"{arm} exploratory {ca}/{cb} model={m} source={other_src}")
                lines.append(f"  - exploratory {other_src}: gap={sum(d) / len(d):+.3f}")
        gap_chart(gaps, title, f"figures/{arm}_gap.png")

    lines.append("\n## Arm 3: coverage by cell (bio personas)\n")
    for m in MODELS:
        cov = coverage_by_cell(judge, m)
        lines.append(f"- {m}: " + ", ".join(
            f"{c}={cov[c]:.3f}" for c in
            ["control", "edu-high", "edu-low", "polished", "rough"] if c in cov))

    arm3_gaps, arm4_gaps = {}, {}
    for m in MODELS:
        d3 = require(coverage_deltas(judge, m, "polished", "rough"),
                     f"arm3 coverage polished/rough model={m}")
        arm3_gaps[m] = (sum(d3) / len(d3), *bootstrap_ci(d3))
        d4 = require(coverage_deltas(judge, m, "jargon-polished", "control"),
                     f"arm4 coverage jargon-polished/control model={m}")
        arm4_gaps[m] = (sum(d4) / len(d4), *bootstrap_ci(d4))
    gap_chart(arm3_gaps, "Arm 3: coverage(polished) - coverage(rough)",
              "figures/arm3_gap.png")
    gap_chart(arm4_gaps, "Arm 4: coverage(jargon-polished) - coverage(lay-polished)",
              "figures/arm4_gap.png")

    # Exploratory decomposition: where does the register cue live?
    # bio-register gap (polished-rough, cue in biography, question pristine)
    # vs question-register gap (control-lay-rough, cue in the ask itself).
    lines.append("\n## Exploratory: bio-register vs question-register gap\n")
    for m in MODELS:
        d_q = coverage_deltas(judge, m, "control", "lay-rough")
        if d_q:
            g3 = arm3_gaps[m][0]
            lines.append(f"- {m}: bio-register gap={g3:+.3f}, "
                         f"question-register gap={sum(d_q) / len(d_q):+.3f} "
                         f"(n={len(d_q)})")

    lines.append("\n## Arm 4: primary + interaction\n")
    for m in MODELS:
        g, lo, hi = arm4_gaps[m]
        d_rough = require(coverage_deltas(judge, m, "jargon-rough", "lay-rough"),
                          f"arm4 coverage jargon-rough/lay-rough model={m}")
        interaction = sum(d_rough) / len(d_rough) - g
        lines.append(f"- {m}: jargon gap={g:+.3f} [{lo:+.3f}, {hi:+.3f}], "
                     f"interaction(rough - polished)={interaction:+.3f}")
        for tag in ["fact", "warning", "action"]:
            dt = coverage_deltas(judge, m, "jargon-polished", "control", questions, tag)
            if dt:
                lines.append(f"  - exploratory {tag}-only gap: {sum(dt) / len(dt):+.3f}")

    lines.append("\n## Pairwise win rates (order-balanced; independent of checklist wording)\n")
    for label, wins in pairwise_scores(judge).items():
        lines.append(f"- {label}:")
        for m in MODELS:
            if m not in wins:
                continue
            score, lo, hi, w, t, l = wins[m]
            lines.append(f"  - {m}: net score={score:+.3f} [{lo:+.3f}, {hi:+.3f}] "
                         f"(A-wins {w} / ties {t} / B-wins {l})")
    fs = first_shown_rate(judge)
    lines.append(f"- position-bias check: first-shown answer wins "
                 f"{fs:.1%} of decisive judgments (0.5 = unbiased)")

    lines.append("\n## Rubric means by cell (1-7, substance dims averaged)\n")
    for m in MODELS:
        lines.append(f"- {m}: {rubric_by_cell(judge, m)}")

    lines.append("\n## Register descriptives (adaptation, not harm)\n")
    for m in MODELS:
        lines.append(f"- {m}: {register_descriptives(advice, m)}")

    lines.append("\n## Parse failures / refusals by persona (signal, not noise)\n")
    lines.append(f"```\n{status_table(mcq)}\n```")

    with open("RESULTS.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote RESULTS.md + figures/")


def analyze_smoke():
    d = run_dir("smoke", create=False)
    mcq = read_jsonl(os.path.join(d, "mcq.jsonl"))
    advice = read_jsonl(os.path.join(d, "advice.jsonl"))
    judge = read_jsonl(os.path.join(d, "judge.jsonl"))
    print("== smoke MCQ status ==")
    print(status_table(mcq))
    for m in MODELS:
        print(f"{m}: control acc={accuracy(mcq, m, 'control'):.2f} "
              f"({len(ok_rows(mcq, m, 'control'))} ok)")
    print("\n== smoke coverage by cell ==")
    for m in MODELS:
        print(m, coverage_by_cell(judge, m))

    # cost: prefer OpenRouter's usage.cost (actual billed) over token x pricing
    pricing = ChatClient().model_pricing()

    def cost_of(rows, mid):
        cost = sum(r["usage"].get("cost") or 0 for r in rows)
        if cost == 0:
            pt = sum(r["usage"].get("prompt_tokens", 0) for r in rows)
            ct = sum(r["usage"].get("completion_tokens", 0) for r in rows)
            p, c = pricing.get(mid, (0, 0))
            cost = pt * p + ct * c
        return cost

    mcq_total = advice_total = 0.0
    for name, mid in MODELS.items():
        mc = cost_of([r for r in mcq if r["model"] == name], mid)
        ac = cost_of([r for r in advice if r["model"] == name], mid)
        mcq_total += mc
        advice_total += ac
        print(f"{name}: smoke cost ${mc + ac:.3f} (mcq ${mc:.3f}, advice ${ac:.3f})")
    mcq_scale, advice_scale = 800 / 5, 20 / 2
    est = mcq_total * mcq_scale + advice_total * advice_scale
    print(f"\nextrapolation: mcq x{mcq_scale:.0f}, advice x{advice_scale:.0f} "
          f"-> estimated full-run generation cost ${est:.2f}; "
          "judge cost scales ~x10 from smoke judge volume. Eyeball before freezing.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        analyze_smoke()
    else:
        analyze_full()


if __name__ == "__main__":
    main()
