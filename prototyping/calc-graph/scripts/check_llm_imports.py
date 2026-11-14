"""Ratchet: no module outside backend/calcgraph/ai/ may import an LLM SDK.

AST-based: catches ``import x``, ``from x import y``, ``__import__("x")`` and
``importlib.import_module("x")`` with a literal name, at any nesting depth (a lazy
import inside a function counts). Exit 1 on any violation, listing file:line.

    uv run python scripts/check_llm_imports.py              # scan the repo
    uv run python scripts/check_llm_imports.py --self-test  # prove it catches each form
"""
from __future__ import annotations

import argparse
import ast
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ALLOWED_DIR = Path("backend/calcgraph/ai")
SKIP_DIRS = {".venv", "venv", "node_modules", ".git", "__pycache__", "data", "dist", "build"}

# Top-level module names of LLM SDKs / LLM orchestration libraries.
LLM_ROOTS = {
    "anthropic", "claude_agent_sdk", "openai", "google.genai", "google.generativeai",
    "google.ai.generativelanguage", "vertexai", "litellm", "mistralai", "cohere", "groq",
    "together", "ollama", "replicate", "langchain", "langchain_core", "langchain_community",
    "langchain_anthropic", "langchain_openai", "langgraph", "llama_index", "instructor",
    "dspy", "huggingface_hub", "transformers", "boto3.bedrock", "bedrock_runtime", "ai21",
    "fireworks", "deepseek", "xai_sdk",
}


def is_llm(name: str | None) -> bool:
    if not name:
        return False
    return any(name == r or name.startswith(r + ".") for r in LLM_ROOTS)


def _literal(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def scan_file(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    except SyntaxError as e:
        return [(e.lineno or 0, f"unparseable ({e.msg}); cannot prove it imports no LLM SDK")]
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [(node.lineno, f"import {a.name}") for a in node.names if is_llm(a.name)]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if is_llm(node.module):
                hits.append((node.lineno, f"from {node.module} import ..."))
            else:  # from google import genai
                hits += [(node.lineno, f"from {node.module} import {a.name}") for a in node.names
                         if node.module and is_llm(f"{node.module}.{a.name}")]
        elif isinstance(node, ast.Call) and node.args:
            f = node.func
            fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if fname in ("__import__", "import_module") and is_llm(_literal(node.args[0])):
                hits.append((node.lineno, f"{fname}({_literal(node.args[0])!r})"))
    return hits


def iter_py(root: Path):
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        yield p, rel


def scan(root: Path) -> tuple[int, list[str], list[str]]:
    n, bad, allowed = 0, [], []
    for p, rel in iter_py(root):
        n += 1
        for line, what in scan_file(p):
            msg = f"{rel}:{line}: {what}"
            (allowed if rel.is_relative_to(ALLOWED_DIR) else bad).append(msg)
    return n, bad, allowed


def self_test() -> int:
    cases = {
        "backend/calcgraph/bad1.py": "import anthropic\n",
        "backend/calcgraph/bad2.py": "from openai import OpenAI\n",
        "scripts/bad3.py": "def f():\n    import litellm\n",
        "synth/bad4.py": "from google import genai\n",
        "backend/calcgraph/bad5.py": "import importlib\nm = importlib.import_module('anthropic')\n",
        "backend/calcgraph/bad6.py": "m = __import__('langchain_core.messages')\n",
        "backend/calcgraph/ok1.py": "import json\nfrom google.protobuf import message\nx = 'anthropic'\n",
        "backend/calcgraph/ok2.py": "from .ai import extract\nfrom calcgraph.ai import providers\n",
        "backend/calcgraph/ai/providers/real.py": "def f():\n    import anthropic\n",
        ".venv/lib/site.py": "import openai\n",
    }
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for rel, src in cases.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(src)
        _, bad, allowed = scan(root)
    flagged = {b.split(":")[0] for b in bad}
    want = {k for k in cases if "/bad" in k}
    ok = flagged == want and len(allowed) == 1 and allowed[0].startswith("backend/calcgraph/ai/")
    print(f"self-test: flagged {sorted(flagged)}; allowed {allowed}")
    print("self-test PASS" if ok else f"self-test FAIL (wanted {sorted(want)})")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--root", type=Path, default=REPO)
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    n, bad, allowed = scan(a.root)
    print(f"scanned {n} .py files; LLM SDK imports inside {ALLOWED_DIR}/: {len(allowed)}")
    for m in allowed:
        print(f"  allowed  {m}")
    if bad:
        print(f"FAIL: {len(bad)} LLM SDK import(s) outside {ALLOWED_DIR}/ - route them through calcgraph.ai:")
        for m in bad:
            print(f"  {m}")
        return 1
    print("PASS: no LLM SDK imports outside calcgraph/ai/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
