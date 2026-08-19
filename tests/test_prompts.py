from prompts import build_mcq_prompt, classify, parse_letter, variant_for


def test_prompt_control_has_no_bio():
    p = build_mcq_prompt(None, "Was X ever solved?", ["No", "Yes", "Maybe"])
    assert p.startswith("Question: Was X ever solved?")
    assert "(A) No" in p and "(B) Yes" in p and "(C) Maybe" in p
    assert "single letter (A, B, or C) and nothing else" in p


def test_prompt_with_bio_prepends_it():
    p = build_mcq_prompt("Hi, my name is Danny.", "Q?", ["a", "b"])
    assert p.startswith("Hi, my name is Danny.")
    assert "\n\nQuestion: Q?" in p
    assert "single letter (A or B) and nothing else" in p


def test_prompt_many_options_uses_range():
    p = build_mcq_prompt(None, "Q?", [str(i) for i in range(10)])
    assert "(J)" in p and "single letter (A–J) and nothing else" in p


def test_parse_letter():
    assert parse_letter("B", 4) == "B"
    assert parse_letter(" (c). ", 4) == "C"
    assert parse_letter("B.", 4) == "B"
    assert parse_letter("E", 4) is None          # out of range
    assert parse_letter("The answer is B", 4) is None
    assert parse_letter("", 4) is None


def test_classify():
    assert classify("A", 4) == "ok"
    assert classify("I'm sorry, I can't help with that.", 4) == "refusal"
    assert classify("Well, it depends on several factors...", 4) == "parse_fail"


def test_variant_rotation():
    assert [variant_for(i) for i in range(6)] == [0, 1, 2, 3, 0, 1]
