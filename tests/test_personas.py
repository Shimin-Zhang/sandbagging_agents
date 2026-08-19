import yaml

BIO_CLASSES = ["edu-high", "edu-low", "polished", "rough"]


def load():
    with open("personas.yaml") as f:
        return yaml.safe_load(f)


def test_structure():
    p = load()
    assert p["control"] is None
    for cls in BIO_CLASSES:
        assert len(p[cls]["variants"]) == 4, cls
    assert "rough_transform" in p


def test_edu_word_counts():
    p = load()
    for cls in ["edu-high", "edu-low"]:
        for v in p[cls]["variants"]:
            n = len(v.split())
            assert 70 <= n <= 130, f"{cls}: {n} words"


def test_rough_is_lowercase_of_paired_content():
    p = load()
    for i, rough in enumerate(p["rough"]["variants"]):
        assert rough == rough.lower(), f"rough v{i} contains uppercase"
        # paired polished variant shares its factual numbers
        polished = p["polished"]["variants"][i]
        pol_digits = [t for t in polished.replace("'", " ").split() if any(c.isdigit() for c in t)]
        for d in pol_digits:
            num = "".join(c for c in d if c.isdigit())
            assert num in rough, f"number {num} missing from rough v{i}"
