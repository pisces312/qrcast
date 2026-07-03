"""Minimize a Python script while keeping it valid.

Strips comments, docstrings, blank lines, and trailing whitespace.
Preserves indentation and string literals.

Usage:
    python -m qrcast.pyminify <input.py>              # print to stdout
    python -m qrcast.pyminify <input.py> -o out.py    # write to file
    python -m qrcast.pyminify <input.py> --stats      # show size reduction
"""

import tokenize
import io
import ast
import sys
import argparse


def minify_python(source: str) -> str:
    """Minify a Python source string, keeping it a valid script.

    - Removes comments
    - Removes docstrings (module, class, function)
    - Removes blank lines
    - Strips trailing whitespace per line
    - Preserves indentation and all non-doc string literals
    """
    source = _remove_docstrings(source)
    source = _remove_comments(source)
    source = _reduce_indentation(source)

    lines = []
    for line in source.splitlines():
        stripped = line.rstrip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines) + "\n"


def _reduce_indentation(source: str) -> str:
    """Replace original indentation with 1-space-per-level."""
    lines = source.splitlines(keepends=True)

    indent_unit = None
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped == "\n":
            continue
        leading = len(line) - len(line.lstrip())
        if leading > 0:
            if indent_unit is None or leading < indent_unit:
                indent_unit = leading

    if not indent_unit or indent_unit <= 1:
        return source

    result = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped == "\n":
            result.append(line)
            continue
        leading = len(line) - len(line.lstrip())
        level = leading // indent_unit
        result.append(" " * level + stripped)
    return "".join(result)


def _remove_docstrings(source: str) -> str:
    """Remove docstrings from module, class, and function bodies."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    remove_lines = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if not body:
                continue
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                for ln in range(first.lineno, first.end_lineno + 1):
                    remove_lines.add(ln)

    if not remove_lines:
        return source

    lines = source.splitlines(keepends=True)
    result = []
    for i, line in enumerate(lines, start=1):
        if i not in remove_lines:
            result.append(line)
    return "".join(result)


def _remove_comments(source: str) -> str:
    """Remove comment tokens using the tokenize module."""
    tokens = []
    try:
        token_gen = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in token_gen:
            if tok.type == tokenize.COMMENT:
                continue
            tokens.append(tok)
    except tokenize.TokenError:
        return source

    return tokenize.untokenize(tokens)


def minify_file(filepath: str) -> str:
    """Read a Python file and return its minified source."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    return minify_python(source)


def main():
    parser = argparse.ArgumentParser(description="Minify a Python script")
    parser.add_argument("input", help="Input Python file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--stats", action="store_true", help="Show size stats")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        original = f.read()

    minified = minify_python(original)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(minified)
        print(f"Written to {args.output}")
    else:
        print(minified)

    if args.stats:
        orig_size = len(original.encode("utf-8"))
        mini_size = len(minified.encode("utf-8"))
        ratio = (1 - mini_size / orig_size) * 100 if orig_size else 0
        print(f"\n--- Stats ---", file=sys.stderr)
        print(f"Original:  {orig_size} bytes", file=sys.stderr)
        print(f"Minified:  {mini_size} bytes", file=sys.stderr)
        print(f"Reduction: {ratio:.1f}%", file=sys.stderr)


if __name__ == "__main__":
    main()
