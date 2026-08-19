import glob

from common import read_jsonl

PHRASINGS = ["lay-polished", "jargon-polished", "lay-rough", "jargon-rough"]
TAGS = {"fact", "warning", "action"}


def advice_files():
    return glob.glob("questions/advice*.jsonl")


def test_smoke_file_exists_with_two_items():
    rows = read_jsonl("questions/advice_smoke.jsonl")
    assert len(rows) == 2
    assert all(r["smoke"] for r in rows)


def test_advice_schema():
    for path in advice_files():
        for r in read_jsonl(path):
            assert "smoke" in r, r["qid"]
            assert set(r["phrasings"]) == set(PHRASINGS), r["qid"]
            assert 3 <= len(r["checklist"]) <= 6, r["qid"]
            for item in r["checklist"]:
                assert item["tag"] in TAGS, (r["qid"], item)
            assert r["substitutions"], r["qid"]


def test_substitutions_respect_register():
    for path in advice_files():
        for r in read_jsonl(path):
            lay_text = r["phrasings"]["lay-polished"].lower()
            jargon_text = r["phrasings"]["jargon-polished"].lower()
            for lay_term, jargon_term in r["substitutions"]:
                assert lay_term.lower() in lay_text, (r["qid"], lay_term)
                assert jargon_term.lower() in jargon_text, (r["qid"], jargon_term)


def test_rough_phrasings_are_lowercase():
    for path in advice_files():
        for r in read_jsonl(path):
            for key in ["lay-rough", "jargon-rough"]:
                assert r["phrasings"][key] == r["phrasings"][key].lower(), (r["qid"], key)
