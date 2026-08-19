# persona_gap

Do LLMs give worse answers to users they think can't check them?

A four-arm experiment measuring how a user's *apparent* education — announced in a
biography, implied by writing register, or signaled by vocabulary — changes both
the accuracy and the substance of what four models answer. A replication and
extension of the sandbagging finding in Appendix C of
[Perez et al. 2022](https://arxiv.org/abs/2212.09251), run in August 2026 for
about $10 in API credits.

**Blog post:** [You are an AI Assistant, but what am I? — Why I tell my Agent I'm an expert at everything](https://shimin.io/journal/why-i-tell-my-agent-im-an-expert-at-everything/)

## TL;DR

- The original multiple-choice effect is mostly closed at the frontier — but
  qwen3-235b (July 2025) still shows it: **+4.5 points of accuracy** between the
  educated and uneducated persona on TruthfulQA [95% CI +2.0, +7.2].
- The bigger effect isn't accuracy, it's **substance**: on 20 stakes-bearing
  advice questions (health, finance, tenant rights, consumer security), every
  model covered fewer must-mention checklist items for the low-education persona
  — a drop below the no-bio baseline, with no matching boost for the professor.
- The frontier model's version is covert: answers of equal length and warmth
  that silently omit the safety-critical items.

## The four arms

1. **Explicit bio × MCQ** — Perez-style biographies (professor vs dropout)
   prepended to 800 questions: 400 TruthfulQA + 200 hard MMLU + 200 hard
   MMLU-Pro (difficulty-filtered by a local Qwen). Metric: paired accuracy gap.
2. **Register × MCQ** — same questions; education-neutral bios written cleanly
   vs with typos/texting shorthand. Does *how you write* move accuracy?
3. **Advice quality** — 20 authored advice questions with frozen 3–6-item
   checklists (facts / warnings / actions), scored by a blinded judge that never
   sees the biography. Metric: checklist coverage per persona.
4. **Jargon × register in the question itself** — no personas; each advice
   question phrased 4 ways (lay/jargon × polished/rough), synonym-level swaps
   only. Pre-registered result: null.

Models (via OpenRouter, providers pinned, reasoning off): `claude-sonnet-5`,
`gpt-5.6-luna-pro`, `deepseek-v4-flash-0731`, `qwen3-235b-a22b-2507` (kept
deliberately as a previous-generation control). Judges from disjoint lineages:
`gemini-3.7-flash` (primary) and `kimi-k2.6` (full 1,920-judgment replication).

The design — arms, personas, metrics, and primary contrasts — was frozen
2026-08-14, before any main-run data was collected.

## Repo map

| path | what it is |
|---|---|
| `run.py`, `judge.py`, `analyze.py`, `rescore.py` | generation, judging, analysis pipeline (idempotent, resumes from partial runs) |
| `build_mcq.py` | builds the 800-question MCQ set (needs the local filter model; output already committed) |
| `prompts.py`, `personas.yaml` | prompt assembly and all persona biographies (4 variants each) |
| `questions/` | frozen stimuli: MCQ set, advice questions with checklists |
| `results/full/20260814-203517/` | **the final run** — all figures and stats derive from this |
| `results/full/20260814-170323/` | first run, kept deliberately: a 1,200-token cap silently truncated answers unequally (see the post's methods note) |
| `results/smoke/` | smoke round, after which checklists were frozen |
| `diagrams.py`, `figures/` | all charts in the post |
| `viewer.py` | local results browser (`uv run python viewer.py`, port 7788) |
| `dev-prompts.md`, `sycophancy-prompts.md` | DIY prompt packs — run the experiment on your own assistant |
| `RESULTS.md` | full numbers: gaps, CIs, flip rates, judge comparisons |

## Reproducing

```sh
uv sync
export OPENROUTER_API_KEY=...
make test        # unit tests, no network
make preflight   # 1-question end-to-end check
make smoke       # small round trip
make all         # full run: generate, judge, analyze (~$8 + ~$2 judging)
uv run python diagrams.py   # rebuild figures from the latest full run
```

Model IDs and pinned providers are in `common.py`; re-verify pricing with
`uv run python run.py --check-models` before a full run. Rebuilding the MCQ set
from scratch (`make questions`) additionally needs a local
Qwen3.6-35B-A3B under llama.cpp (`make filter-server`) — not required if you
use the committed `questions/mcq.jsonl`.

## License

Code, prompts, and documentation: [MIT](LICENSE).

The question files in `questions/` derive from
[TruthfulQA](https://github.com/sylinrl/TruthfulQA) (Apache-2.0),
[MMLU](https://github.com/hendrycks/test) (MIT), and
[MMLU-Pro](https://github.com/TIGER-AI-Lab/MMLU-Pro) (Apache-2.0), and retain
their upstream licenses. Files under `results/` are model outputs collected via
the OpenRouter API, included for reproducibility and audit.
