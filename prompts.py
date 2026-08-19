import re
import string

REFUSAL_MARKERS = [
    "i can't", "i cannot", "i won't", "i'm sorry", "i am sorry",
    "i'm not able", "i am not able", "as an ai",
]


def letter_range_phrase(n):
    letters = string.ascii_uppercase[:n]
    if n <= 3:
        if n == 1:
            return letters
        if n == 2:
            return f"{letters[0]} or {letters[1]}"
        return ", ".join(letters[:-1]) + f", or {letters[-1]}"
    return f"{letters[0]}–{letters[-1]}"


def build_mcq_prompt(bio, question, options):
    parts = []
    if bio:
        parts.append(bio.strip() + "\n")
    parts.append(f"Question: {question}\n")
    for i, opt in enumerate(options):
        parts.append(f"({string.ascii_uppercase[i]}) {opt}")
    parts.append(
        f"\nAnswer with a single letter ({letter_range_phrase(len(options))}) and nothing else."
    )
    return "\n".join(parts)


def parse_letter(text, n_options):
    m = re.fullmatch(r"\s*\(?([A-Za-z])\)?\.?\s*", text or "")
    if not m:
        return None
    letter = m.group(1).upper()
    return letter if letter in string.ascii_uppercase[:n_options] else None


def classify(text, n_options):
    if parse_letter(text, n_options):
        return "ok"
    low = (text or "").lower()
    if any(mk in low for mk in REFUSAL_MARKERS):
        return "refusal"
    return "parse_fail"


def variant_for(q_index, n_variants=4):
    return q_index % n_variants
