"""Quick-and-dirty results browser. Usage: uv run python viewer.py [port]

Serves http://127.0.0.1:7788 — lists runs under results/, click into MCQ
tables and advice transcripts with judge verdicts inline. Read-only.
"""
import glob
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

_cache = {}


def rows(path):
    if not os.path.exists(path):
        return []
    key = (path, os.path.getmtime(path))
    if key not in _cache:
        _cache.clear()
        with open(path) as f:
            _cache[key] = [json.loads(l) for l in f if l.strip()]
    return _cache[key]


def safe_dir(d):
    real = os.path.realpath(os.path.join("results", d))
    if not real.startswith(os.path.realpath("results") + os.sep):
        raise ValueError("bad path")
    return real


def esc(s):
    return html.escape(str(s))


PAGE = """<!doctype html><meta charset=utf-8><title>persona_gap results</title>
<style>
body{{font:14px/1.5 monospace;margin:2em auto;max-width:70em;padding:0 1em;color:#222}}
table{{border-collapse:collapse;margin:1em 0}} td,th{{border:1px solid #bbb;padding:.3em .6em;text-align:left}}
a{{color:#06c}} .ok{{color:#080}} .bad{{color:#c00;font-weight:bold}} .miss{{background:#fdd}}
pre{{white-space:pre-wrap;background:#f6f6f6;padding:1em;border:1px solid #ddd}}
h2{{border-bottom:2px solid #222}} .tag{{color:#666;font-size:12px}}
</style><body><p><a href=/>&larr; runs</a></p>{body}"""


def page(handler, body, code=200):
    data = PAGE.format(body=body).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(data)


def index():
    out = ["<h2>runs</h2><table><tr><th>run</th><th>mcq</th><th>advice</th><th>judge</th></tr>"]
    for d in sorted(glob.glob("results/*/*")):
        if os.path.islink(d) or not os.path.isdir(d):
            continue
        rel = os.path.relpath(d, "results")
        counts = [len(rows(os.path.join(d, f + ".jsonl"))) for f in ("mcq", "advice", "judge")]
        out.append(f"<tr><td><a href='/run?d={esc(rel)}'>{esc(rel)}</a></td>"
                   + "".join(f"<td>{c}</td>" for c in counts) + "</tr>")
    out.append("</table><h2>question sets</h2><ul>")
    for f in sorted(glob.glob("questions/*.jsonl")):
        name = os.path.basename(f)[:-6]
        n = len(rows(f))
        if name.startswith("advice"):
            out.append(f"<li><a href='/questions?f={esc(name)}'>{esc(name)}</a> ({n} items)</li>")
        else:
            srcs = sorted({r["qid"].split("-")[0] for r in rows(f)})
            links = " · ".join(f"<a href='/questions?f={esc(name)}&src={esc(s)}'>{esc(s)}</a>"
                               for s in srcs)
            out.append(f"<li>{esc(name)} ({n} items): {links}</li>")
    out.append("</ul>")
    return "".join(out)


def questions_view(fname, src):
    if "/" in fname or ".." in fname:
        raise ValueError("bad file")
    items = rows(f"questions/{fname}.jsonl")
    out = [f"<h2>questions — {esc(fname)}{' / ' + esc(src) if src else ''}</h2>"]
    if fname.startswith("advice"):
        for q in items:
            out.append(f"<h3>{esc(q['qid'])} <span class=tag>({esc(q['domain'])})</span></h3>")
            out.append("<table>")
            for k in ["lay-polished", "jargon-polished", "lay-rough", "jargon-rough"]:
                out.append(f"<tr><th>{esc(k)}</th><td>{esc(q['phrasings'][k])}</td></tr>")
            out.append("</table><p><b>checklist:</b></p><table>")
            for c in q["checklist"]:
                out.append(f"<tr><td class=tag>{esc(c['tag'])}</td><td>{esc(c['text'])}</td></tr>")
            out.append("</table><p><b>substitutions:</b> " + " · ".join(
                f"“{esc(a)}” ↔ “{esc(b)}”" for a, b in q["substitutions"]) + "</p>")
    else:
        sel = [q for q in items if not src or q["qid"].startswith(src + "-")]
        out.append(f"<p>{len(sel)} questions</p>")
        for q in sel:
            opts = "".join(f"<li>{'<b>' if i == q['answer_idx'] else ''}"
                           f"({chr(65 + i)}) {esc(o)}"
                           f"{' ✓</b>' if i == q['answer_idx'] else ''}</li>"
                           for i, o in enumerate(q["options"]))
            out.append(f"<details><summary>{esc(q['qid'])} — {esc(q['question'])[:110]}</summary>"
                       f"<p>{esc(q['question'])}</p><ul>{opts}</ul></details>")
    return "".join(out)


def run_view(d):
    base = safe_dir(d)
    mcq, adv = rows(f"{base}/mcq.jsonl"), rows(f"{base}/advice.jsonl")
    jr = rows(f"{base}/judge.jsonl")
    cov = {(r["model"], r["qid"], r["cell"]): r for r in jr if r["task"] == "coverage"}
    models = sorted({r["model"] for r in mcq + adv})
    out = [f"<h2>{esc(d)}</h2>"]

    if mcq:
        cells = sorted({r["cell"] for r in mcq})
        out.append("<h3>mcq — acc (ok/total), click for rows</h3><table><tr><th></th>"
                   + "".join(f"<th>{esc(c)}</th>" for c in cells) + "</tr>")
        for m in models:
            tds = []
            for c in cells:
                sel = [r for r in mcq if r["model"] == m and r["cell"] == c]
                ok = [r for r in sel if r["status"] == "ok"]
                acc = sum(r["correct"] for r in ok) / len(ok) if ok else float("nan")
                cls = "ok" if len(ok) == len(sel) else "bad"
                tds.append(f"<td class={cls}><a href='/mcq?d={esc(d)}&model={esc(m)}&cell={esc(c)}'>"
                           f"{acc:.2f} ({len(ok)}/{len(sel)})</a></td>")
            out.append(f"<tr><th>{esc(m)}</th>{''.join(tds)}</tr>")
        out.append("</table>")

    if adv:
        qids = sorted({r["qid"] for r in adv})
        cells = sorted({r["cell"] for r in adv})
        out.append("<h3>advice — coverage per transcript, click to read</h3>"
                   "<p class=tag>the control cell is the bare lay-polished question "
                   "(no biography) — it doubles as arm 4's lay-polished baseline</p>")
        for qid in qids:
            hdr = {"control": "control<br><span class=tag>(= lay-polished)</span>"}
            out.append(f"<h4>{esc(qid)}</h4><table><tr><th></th>"
                       + "".join(f"<th>{hdr.get(c, esc(c))}</th>" for c in cells) + "</tr>")
            for m in models:
                tds = []
                for c in cells:
                    if (m, qid, c) not in {(r["model"], r["qid"], r["cell"]) for r in adv}:
                        tds.append("<td>–</td>")
                        continue
                    v = cov.get((m, qid, c))
                    label = "?"
                    cls = ""
                    if v:
                        items = v["items"]
                        n_ok = sum(bool(x) for x in items.values())
                        label = f"{n_ok}/{len(items)}"
                        cls = "ok" if n_ok == len(items) else "bad"
                    tds.append(f"<td class='{cls}'><a href='/advice?d={esc(d)}&model={esc(m)}"
                               f"&qid={esc(qid)}&cell={esc(c)}'>{label}</a></td>")
                out.append(f"<tr><th>{esc(m)}</th>{''.join(tds)}</tr>")
            out.append("</table>")
    return "".join(out)


def mcq_view(d, model, cell):
    base = safe_dir(d)
    sel = [r for r in rows(f"{base}/mcq.jsonl") if r["model"] == model and r["cell"] == cell]
    out = [f"<h2>{esc(d)} — mcq — {esc(model)} / {esc(cell)}</h2>"]
    for r in sel:
        cls = "ok" if r["status"] == "ok" else "bad"
        mark = "✓" if r["correct"] else "✗"
        out.append(f"<details><summary class={cls}>{esc(r['qid'])} [{esc(r['source'])}] "
                   f"letter={esc(r['letter'])} {mark} status={esc(r['status'])}</summary>"
                   f"<pre>{esc(r.get('prompt', '(prompt not recorded)'))}</pre>"
                   f"<p>raw reply: <code>{esc(r['raw'])!s}</code></p></details>")
    return "".join(out)


def advice_view(d, model, qid, cell):
    base = safe_dir(d)
    row = next((r for r in rows(f"{base}/advice.jsonl")
                if (r["model"], r["qid"], r["cell"]) == (model, qid, cell)), None)
    if not row:
        return "<p>not found</p>"
    jr = rows(f"{base}/judge.jsonl")
    cov = next((r for r in jr if r["task"] == "coverage"
                and (r["model"], r["qid"], r["cell"]) == (model, qid, cell)), None)
    rub = next((r for r in jr if r["task"] == "rubric"
                and (r["model"], r["qid"], r["cell"]) == (model, qid, cell)), None)
    checklists = {q["qid"]: q["checklist"] for src in glob.glob("questions/advice*.jsonl")
                  for q in rows(src)}
    out = [f"<h2>{esc(qid)} — {esc(model)} / {esc(cell)}</h2>",
           f"<h3>prompt</h3><pre>{esc(row.get('prompt', '(not recorded)'))}</pre>",
           f"<h3>response</h3><pre>{esc(row['response'])}</pre>"]
    if cov:
        out.append("<h3>judge: checklist</h3><table>")
        for c in checklists.get(qid, []):
            hit = cov["items"].get(c["id"])
            cls = "" if hit else "miss"
            out.append(f"<tr class='{cls}'><td>{'✓' if hit else '✗'}</td>"
                       f"<td class=tag>{esc(c['tag'])}</td><td>{esc(c['text'])}</td></tr>")
        out.append("</table>")
    if rub:
        out.append("<h3>judge: rubric</h3><p>" + ", ".join(
            f"{esc(k)}={v}" for k, v in rub["scores"].items()) + "</p>")
    pw = [r for r in jr if r["task"] == "pairwise" and r["model"] == model
          and r["qid"] == qid and cell in r["pair"]]
    if pw:
        out.append("<h3>judge: pairwise involving this cell</h3><ul>")
        for r in pw:
            out.append(f"<li>{esc(r['pair'][0])} vs {esc(r['pair'][1])} "
                       f"(order {r['order']}): winner <b>{esc(r['winner'])}</b></li>")
        out.append("</ul>")
    return "".join(out)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/":
                page(self, index())
            elif u.path == "/run":
                page(self, run_view(q["d"]))
            elif u.path == "/mcq":
                page(self, mcq_view(q["d"], q["model"], q["cell"]))
            elif u.path == "/advice":
                page(self, advice_view(q["d"], q["model"], q["qid"], q["cell"]))
            elif u.path == "/questions":
                page(self, questions_view(q["f"], q.get("src")))
            else:
                page(self, "<p>404</p>", 404)
        except Exception as e:  # quick-and-dirty: show the error, keep serving
            page(self, f"<pre>error: {esc(e)}</pre>", 500)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7788
    print(f"viewer: http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
