PY = uv run python

test:
	uv run pytest -q

questions:
	$(PY) build_mcq.py

preflight:
	$(PY) run.py --check-models
	$(PY) run.py --smoke --limit 1 --only-model sonnet
	$(PY) judge.py --smoke --limit 1 --only-model sonnet
	$(PY) analyze.py --smoke

smoke:
	$(PY) run.py --check-models
	$(PY) run.py --smoke
	$(PY) judge.py --smoke
	$(PY) analyze.py --smoke

run:
	$(PY) run.py

judge:
	$(PY) judge.py

analyze:
	$(PY) analyze.py

all: run judge analyze

filter-server:
	~/ai/llama.cpp/build/bin/llama-server \
	  -m ~/ai/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
	  --port 8090 -ngl 99 -c 4096 --reasoning-budget 0

.PHONY: test questions preflight smoke run judge analyze all filter-server
