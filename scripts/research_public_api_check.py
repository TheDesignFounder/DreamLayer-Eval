"""Require public research functions to have docstrings and complete type signatures."""

import ast
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    failures, checked = [], 0
    for path in sorted((root / "research").glob("*.py")):
        tree = ast.parse(path.read_text())
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                functions.extend(
                    member
                    for member in node.body
                    if isinstance(member, ast.FunctionDef)
                    and (not member.name.startswith("_") or member.name == "__init__")
                )
        for function in functions:
            checked += 1
            args = function.args
            parameters = [
                *args.posonlyargs,
                *args.args,
                *args.kwonlyargs,
                *([args.vararg] if args.vararg else []),
                *([args.kwarg] if args.kwarg else []),
            ]
            missing = [
                p.arg for p in parameters if p.arg not in {"self", "cls"} and p.annotation is None
            ]
            if not ast.get_docstring(function) or function.returns is None or missing:
                failures.append(
                    f"{path.name}:{function.lineno} {function.name}: docstring/return/parameters missing ({missing})"
                )
    print(f"Checked {checked} public function signatures and docstrings")
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
