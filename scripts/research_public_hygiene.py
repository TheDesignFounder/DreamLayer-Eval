"""Check published research docs for local paths, broken links and raw run artifacts."""

import re
from pathlib import Path
from urllib.parse import unquote


def main():
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "README.md",
        *(root / "docs").rglob("*.md"),
        *(root / "docs/validation").glob("*.json"),
        *(root / "examples/research-v1").glob("*"),
    ]
    local_path = re.compile(r"/(?:Users|home)/[^\s/]+|[A-Z]:\\Users\\", re.I)
    failures = []
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text()
        if local_path.search(text):
            failures.append(f"Local user path in {path.relative_to(root)}")
        # Existing unrelated documentation links are outside this research check.
        if path.name.startswith("research-") or path == root / "README.md":
            for link in re.findall(r"\]\(([^)]+)\)", text):
                target = unquote(link.split("#", 1)[0].strip("<>"))
                if (
                    target
                    and not re.match(r"[a-z]+:", target)
                    and not (path.parent / target).exists()
                ):
                    failures.append(f"Broken link in {path.relative_to(root)}: {target}")
    published = [p for p in (root / "docs/validation").rglob("*") if p.is_file()]
    if any(p.suffix != ".json" for p in published):
        failures.append("docs/validation must contain portable summary JSON only")
    size = sum(p.stat().st_size for p in published)
    if size > 250_000:
        failures.append("Published validation summaries exceed 250 KB")
    print(
        f"Checked {len(targets)} public documents/examples; {len(published)} validation summaries ({size} bytes)"
    )
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
