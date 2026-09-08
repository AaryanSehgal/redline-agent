"""Turn contract text into clause dicts.

In:  one string (the whole contract)
Out: list of clause dicts -- Stage 2, the shape core.py expects
"""

import re


def parse(text):
    """Contract text in, list of clause dicts out."""
    text = re.sub(r"[ \t]+", " ", text)

    starts = list(re.finditer(r"^\d+\.\d+", text, re.MULTILINE))

    clauses = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        number = m.group()

        rest = text[m.end():end].strip()
        heading, _, body = rest.partition(".")
        body = body.strip()

        found = re.findall(r"\d+\.\d+", body)
        refs = sorted(set(r for r in found if r != number))

        clauses.append({
            "id": f"cl{i + 1}",
            "number": number,
            "heading": heading.strip(),
            "text": body,
            "category": None,
            "refs": refs,
        })

    return clauses

if __name__ == "__main__":
    with open("data/sample_contract.txt", encoding="utf-8") as f:
        clauses = parse(f.read())

    for c in clauses:
        print(c["number"], "|", c["heading"], "|", c["refs"])