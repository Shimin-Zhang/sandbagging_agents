import tomllib


def test_deps_present():
    with open("pyproject.toml", "rb") as f:
        proj = tomllib.load(f)
    deps = " ".join(proj["project"]["dependencies"])
    for pkg in ["httpx", "pyyaml", "datasets", "numpy", "matplotlib", "textstat"]:
        assert pkg in deps, f"missing dependency {pkg}"
