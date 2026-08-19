"""Result diagrams: model-by-arm forest grid, coverage heatmap, length scatter.

Usage: uv run python diagrams.py   (writes figures/*.png from the latest full run)
"""
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze import bootstrap_ci, coverage_deltas, paired_deltas, pairwise_scores
from common import read_jsonl, run_dir

MODELS = ["sonnet", "luna", "dsflash", "qwen"]
LABEL = {"sonnet": "claude-sonnet-5", "luna": "gpt-5.6-luna-pro",
         "dsflash": "deepseek-v4-flash", "qwen": "qwen3-235b"}
COLOR = {"sonnet": "#d97706", "luna": "#0d9488", "dsflash": "#2563eb", "qwen": "#7c3aed"}
CELLS = ["control", "edu-high", "edu-low", "polished", "rough",
         "jargon-polished", "lay-rough", "jargon-rough"]


def est(deltas, n_boot=5000):
    m = sum(deltas) / len(deltas)
    lo, hi = bootstrap_ci(deltas, n_boot=n_boot)
    return m, lo, hi


def forest(mcq, j1, j2):
    def cov_est(jr, a, b):
        return {m: est(coverage_deltas(jr, m, a, b)) for m in MODELS}

    pw1, pw2 = pairwise_scores(j1), pairwise_scores(j2)
    pw = lambda p: {m: p["arm3-education"][m][:3] for m in MODELS}
    panels = [
        ("Arm 1 — explicit bio\nMCQ accuracy gap (TruthfulQA)",
         {m: est(paired_deltas(mcq, m, "edu-high", "edu-low", "truthfulqa")) for m in MODELS}, None),
        ("Arm 2 — register bio\nMCQ accuracy gap (TruthfulQA)",
         {m: est(paired_deltas(mcq, m, "polished", "rough", "truthfulqa")) for m in MODELS}, None),
        ("Arm 3 — education\nadvice coverage gap",
         cov_est(j1, "edu-high", "edu-low"), cov_est(j2, "edu-high", "edu-low")),
        ("Arm 3 — register\nadvice coverage gap",
         cov_est(j1, "polished", "rough"), cov_est(j2, "polished", "rough")),
        ("Arm 4 — jargon\nadvice coverage gap",
         cov_est(j1, "jargon-polished", "control"), cov_est(j2, "jargon-polished", "control")),
        ("Arm 3 — education\npairwise net score", pw(pw1), pw(pw2)),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6.8), sharey=True)
    for ax, (title, gem, kim) in zip(axes.flat, panels):
        for i, m in enumerate(MODELS):
            y = len(MODELS) - 1 - i
            g = gem[m]
            off = 0.16 if kim else 0.0
            ax.errorbar(g[0], y + off, xerr=[[g[0] - g[1]], [g[2] - g[0]]],
                        fmt="o", ms=6, capsize=3, color=COLOR[m], lw=1.6)
            if kim:
                k = kim[m]
                ax.errorbar(k[0], y - off, xerr=[[k[0] - k[1]], [k[2] - k[0]]],
                            fmt="D", ms=5.5, capsize=3, color=COLOR[m],
                            mfc="white", lw=1.2, alpha=0.9)
        ax.axvline(0, color="#333", lw=0.8, zorder=0)
        ax.set_title(title, fontsize=9.5)
        ax.set_yticks(range(len(MODELS)))
        ax.set_yticklabels([LABEL[m] for m in reversed(MODELS)], fontsize=9)
        ax.grid(axis="x", alpha=0.25, lw=0.5)
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle("persona_gap: how each model treats each manipulation "
                 "(dot right of zero = the higher-status persona got the better answer)",
                 fontsize=11)
    fig.text(0.5, 0.015,
             "filled circle = gemini-3.7-flash judge · open diamond = kimi-k2.6 second judge"
             " · whiskers = 95% paired-bootstrap CI",
             ha="center", fontsize=8.5, color="#444")
    fig.tight_layout(rect=[0, 0.035, 1, 0.94])
    fig.savefig("figures/overview_forest.png", dpi=170)
    plt.close(fig)


def combined(mcq, j1):
    """All four arms' pre-registered primaries on one axes, colored by arm
    (seaborn 'deep' palette), grouped by model."""
    ARM_COLOR = {"Arm 1 · explicit bio (MCQ acc)": "#4C72B0",
                 "Arm 2 · register bio (MCQ acc)": "#DD8452",
                 "Arm 3 · register bio (advice coverage)": "#55A868",
                 "Arm 4 · jargon phrasing (advice coverage)": "#C44E52"}
    arms = [
        ("Arm 1 · explicit bio (MCQ acc)",
         {m: est(paired_deltas(mcq, m, "edu-high", "edu-low", "truthfulqa")) for m in MODELS}),
        ("Arm 2 · register bio (MCQ acc)",
         {m: est(paired_deltas(mcq, m, "polished", "rough", "truthfulqa")) for m in MODELS}),
        ("Arm 3 · register bio (advice coverage)",
         {m: est(coverage_deltas(j1, m, "polished", "rough")) for m in MODELS}),
        ("Arm 4 · jargon phrasing (advice coverage)",
         {m: est(coverage_deltas(j1, m, "jargon-polished", "control")) for m in MODELS}),
    ]
    fig, ax = plt.subplots(figsize=(9, 6.2))
    n_arms = len(arms)
    yticks, ylabels = [], []
    for gi, m in enumerate(MODELS):
        base = (len(MODELS) - 1 - gi) * (n_arms + 1.2)
        yticks.append(base + (n_arms - 1) / 2)
        ylabels.append(LABEL[m])
        for ai, (name, vals) in enumerate(arms):
            v, lo, hi = vals[m]
            y = base + (n_arms - 1 - ai)
            ax.errorbar(v, y, xerr=[[v - lo], [hi - v]], fmt="o", ms=7, capsize=3.5,
                        color=ARM_COLOR[name], lw=1.8,
                        label=name if gi == 0 else None)
        if gi < len(MODELS) - 1:
            ax.axhline(base - 1.1, color="#ddd", lw=0.8)
    ax.axvline(0, color="#333", lw=0.9, zorder=0)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=10)
    ax.set_xlabel("gap: higher-status persona − lower-status persona "
                  "(right of zero = better answers for higher status)", fontsize=9.5)
    ax.set_title("The four pre-registered primary gaps, per model\n"
                 "(95% paired-bootstrap CIs; primary judge for coverage arms)",
                 fontsize=11)
    ax.legend(loc="lower right", fontsize=8.5, framealpha=0.95)
    ax.grid(axis="x", alpha=0.25, lw=0.5)
    fig.tight_layout()
    fig.savefig("figures/arms_combined.png", dpi=170)
    plt.close(fig)


def detail_grid(rows, title, xlabel, path, scale=100):
    """Dot-and-CI grid grouped by model, annotated point estimates. scale=100
    plots percentage points; scale=1 plots raw fractions.
    rows: [(label, color, {model: (est, lo, hi)})] in display order."""
    n = len(rows)
    fmt = "{:+.1f}" if scale == 100 else "{:+.2f}"
    fig, ax = plt.subplots(figsize=(9, 2.6 + 1.2 * n))
    yticks, ylabels = [], []
    for gi, m in enumerate(MODELS):
        base = (len(MODELS) - 1 - gi) * (n + 1.2)
        yticks.append(base + (n - 1) / 2)
        ylabels.append(LABEL[m])
        for ri, row in enumerate(rows):
            label, color, vals = row[:3]
            vals2 = row[3] if len(row) > 3 else None
            y = base + (n - 1 - ri)
            off = 0.2 if vals2 else 0.0
            v, lo, hi = (scale * x for x in vals[m])
            ax.errorbar(v, y + off, xerr=[[v - lo], [hi - v]], fmt="o", ms=7,
                        capsize=3.5, color=color, lw=1.8,
                        label=label if gi == 0 else None)
            ax.annotate(fmt.format(v), (hi, y + off), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=8.5,
                        color=color)
            if vals2:
                k, klo, khi = (scale * x for x in vals2[m])
                ax.errorbar(k, y - off, xerr=[[k - klo], [khi - k]], fmt="D",
                            ms=5.5, capsize=3, color=color, mfc="white", lw=1.2,
                            alpha=0.9)
                ax.annotate(fmt.format(k), (khi, y - off), xytext=(6, 0),
                            textcoords="offset points", va="center", fontsize=7,
                            color=color, alpha=0.85)
        if gi < len(MODELS) - 1:
            ax.axhline(base - 1.1, color="#ddd", lw=0.8)
    ax.axvline(0, color="#333", lw=0.9, zorder=0)
    ax.margins(x=0.14)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=10)
    ax.set_xlabel(xlabel, fontsize=9.5)
    ax.set_title(title, fontsize=11)
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=2,
               fontsize=8.5, framealpha=0.95)
    ax.grid(axis="x", alpha=0.25, lw=0.5)
    fig.tight_layout(rect=[0, 0.06 if n > 4 else 0.05, 1, 1])
    fig.savefig(path, dpi=170)
    plt.close(fig)


def mcq_detail(mcq, hi, lo, title, path, tqa_row=True):
    """One MCQ arm in detail: primary gap (pooled, optionally TruthfulQA-only)
    plus each side's diff vs the bare-question control."""
    comps = [
        (f"{hi} − {lo} (primary gap, all 800)", "#4C72B0", hi, lo, None),
        (f"{hi} − {lo} (TruthfulQA 400 only)", "#64B5CD", hi, lo, "truthfulqa"),
        (f"{hi} − control (boost above baseline)", "#55A868", hi, "control", None),
        (f"control − {lo} (drop below baseline)", "#C44E52", "control", lo, None),
    ]
    if not tqa_row:
        comps = [c for c in comps if c[4] is None]
    rows = [(label, color, {m: est(paired_deltas(mcq, m, a, b, src)) for m in MODELS})
            for label, color, a, b, src in comps]
    detail_grid(rows,
                title + "\n(400 TruthfulQA + 200 hard MMLU + 200 hard MMLU-Pro; "
                "95% paired-bootstrap CIs)",
                "accuracy gap, percentage points "
                "(right of zero = the higher-status side answered more accurately)",
                path)


def arm3_detail(j1, j2):
    """Arm 3 advice coverage: education contrast decomposed against control,
    both judges overlaid."""
    comps = [
        ("edu-high − edu-low (education gap)", "#4C72B0", "edu-high", "edu-low"),
        ("edu-high − control (boost above baseline)", "#55A868", "edu-high", "control"),
        ("control − edu-low (drop below baseline)", "#C44E52", "control", "edu-low"),
    ]
    rows = [(label, color,
             {m: est(coverage_deltas(j1, m, a, b)) for m in MODELS},
             {m: est(coverage_deltas(j2, m, a, b)) for m in MODELS})
            for label, color, a, b in comps]
    detail_grid(rows,
                "Sandbagging Effect of Explicit Bio on Advice Checklist Coverage\n"
                "(20 stakes-bearing advice questions; 95% paired-bootstrap CIs;\n"
                "filled circle = gemini-3.7-flash primary judge · "
                "open diamond = kimi-k2.6 second judge)",
                "coverage gap, fraction of checklist items covered "
                "(right of zero = higher-status side more complete)",
                "figures/arm3_sandbagging.png", scale=1)


def arm4_detail(j1, j2):
    """Arm 4 jargon × register (question phrasing, no personas): both main
    effects at each level of the other factor, vs the lay-polished control."""
    comps = [
        ("jargon-polished − control (jargon gap, polished phrasing — primary)",
         "#4C72B0", "jargon-polished", "control"),
        ("jargon-rough − lay-rough (jargon gap, rough phrasing)",
         "#64B5CD", "jargon-rough", "lay-rough"),
        ("control − lay-rough (rough drop, lay phrasing)",
         "#C44E52", "control", "lay-rough"),
        ("jargon-polished − jargon-rough (rough drop, jargon phrasing)",
         "#DE9A9C", "jargon-polished", "jargon-rough"),
    ]
    rows = [(label, color,
             {m: est(coverage_deltas(j1, m, a, b)) for m in MODELS},
             {m: est(coverage_deltas(j2, m, a, b)) for m in MODELS})
            for label, color, a, b in comps]
    detail_grid(rows,
                "Sandbagging Effect of Question Phrasing (Jargon × Register) "
                "on Advice Coverage\n"
                "(20 advice questions × 4 phrasings, no personas; "
                "95% paired-bootstrap CIs;\n"
                "filled circle = gemini-3.7-flash primary judge · "
                "open diamond = kimi-k2.6 second judge)",
                "coverage gap, fraction of checklist items covered "
                "(right of zero = higher-status phrasing more complete)",
                "figures/arm4_sandbagging.png", scale=1)


def heatmap(j1):
    per = defaultdict(list)
    for r in j1:
        if r["task"] == "coverage":
            v = list(r["items"].values())
            per[(r["model"], r["cell"])].append(sum(map(bool, v)) / len(v))
    mat = [[sum(per[(m, c)]) / len(per[(m, c)]) for c in CELLS] for m in MODELS]
    fig, ax = plt.subplots(figsize=(10.5, 3.6))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0.5, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(CELLS)))
    ax.set_xticklabels(CELLS, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(MODELS)))
    ax.set_yticklabels([LABEL[m] for m in MODELS], fontsize=9)
    for i in range(len(MODELS)):
        for jx in range(len(CELLS)):
            ax.text(jx, i, f"{mat[i][jx]:.2f}", ha="center", va="center", fontsize=8.5)
    ax.set_title("Advice checklist coverage by persona/phrasing cell (primary judge)",
                 fontsize=10.5)
    fig.colorbar(im, ax=ax, shrink=0.8, label="mean coverage")
    fig.tight_layout()
    fig.savefig("figures/coverage_heatmap.png", dpi=170)
    plt.close(fig)


def length_scatter(adv, j1):
    per_cov = defaultdict(list)
    for r in j1:
        if r["task"] == "coverage":
            v = list(r["items"].values())
            per_cov[(r["model"], r["cell"])].append(sum(map(bool, v)) / len(v))
    per_words = defaultdict(list)
    for r in adv:
        per_words[(r["model"], r["cell"])].append(len(r["response"].split()))
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    for m in MODELS:
        xs, ys = [], []
        for c in CELLS:
            w = sum(per_words[(m, c)]) / len(per_words[(m, c)])
            cv = sum(per_cov[(m, c)]) / len(per_cov[(m, c)])
            xs.append(w)
            ys.append(cv)
            marker = "*" if c == "edu-low" else "o"
            size = 190 if c == "edu-low" else 45
            ax.scatter(w, cv, s=size, marker=marker, color=COLOR[m],
                       edgecolor="black" if c == "edu-low" else "none",
                       linewidth=0.8, zorder=3 if c == "edu-low" else 2)
        ax.plot(xs, ys, color=COLOR[m], alpha=0.25, lw=1, zorder=1)
        ax.annotate(LABEL[m], (xs[0], ys[0]), fontsize=8.5, color=COLOR[m],
                    xytext=(4, 6), textcoords="offset points")
    ax.set_xlabel("mean answer length (words)")
    ax.set_ylabel("mean checklist coverage")
    ax.set_title("Overt vs covert degradation: the starred point is the edu-low cell\n"
                 "(deepseek halves its answers for Danny; sonnet keeps length and drops substance)",
                 fontsize=10)
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    fig.savefig("figures/length_vs_coverage.png", dpi=170)
    plt.close(fig)


def main():
    d = run_dir("full", create=False)
    mcq = read_jsonl(os.path.join(d, "mcq.jsonl"))
    adv = read_jsonl(os.path.join(d, "advice.jsonl"))
    j1 = read_jsonl(os.path.join(d, "judge.jsonl"))
    j2 = read_jsonl(os.path.join(d, "judge2.jsonl"))
    os.makedirs("figures", exist_ok=True)
    forest(mcq, j1, j2)
    combined(mcq, j1)
    mcq_detail(mcq, "edu-high", "edu-low",
               "Sandbagging Effect of Explicit Bio on 800 MCQ",
               "figures/arm1_sandbagging.png")
    mcq_detail(mcq, "polished", "rough",
               "Sandbagging Effect of Implicit Register Bio on 800 MCQ",
               "figures/arm2_sandbagging.png", tqa_row=False)
    arm3_detail(j1, j2)
    arm4_detail(j1, j2)
    heatmap(j1)
    length_scatter(adv, j1)
    print("wrote figures/overview_forest.png, arms_combined.png, "
          "arm1_sandbagging.png, arm2_sandbagging.png, arm3_sandbagging.png, "
          "arm4_sandbagging.png, coverage_heatmap.png, length_vs_coverage.png")


if __name__ == "__main__":
    main()
