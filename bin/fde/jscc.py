#!/usr/bin/env python3
"""
jscc — cyclomatic complexity of TypeScript and JavaScript functions,
stdlib only (I6), from tokens, the way Lizard measures C-family code: no
parser to install in the client.

A function is a `function` declaration or expression, a method or
constructor (`name(...) {` in a class or object), a getter or setter, or
an arrow — with a block body, or an expression body that runs to the
`,`, `;` or closing bracket that ends it (ESLint counts each inline
`() => a && b` of a component as its own function, and so does this).
Complexity is 1 + each decision in the body, nested functions excluded:
`if`, `for`, `while`, `case`, `catch`, the conditional `? :`, `&&`,
`||`, `??` and their assignments, each `?.`, and each default value in a
parameter list or a destructuring — ESLint's `complexity` rule (v10),
against which this was calibrated on two client projects.

Strings, comments, template text and regular expressions are skipped. A
quote does not run past its line, so an apostrophe in JSX text costs at
most that line.
"""
from __future__ import annotations

import hashlib
import re

SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
CONTROL = {"if", "for", "while", "switch", "catch", "with", "return", "typeof",
           "await", "yield", "new", "in", "of", "do", "else", "case", "throw",
           "delete", "void", "instanceof"}
DECISION_WORDS = {"if", "for", "while", "case", "catch"}
DECISION_OPS = {"&&", "||", "??", "&&=", "||=", "??="}
OPS = sorted(["===", "!==", "**=", "<<=", ">>=", ">>>", "&&=", "||=", "??=", "...",
              "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=",
              "-=", "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>"],
             key=len, reverse=True)
REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^") | {"return", "typeof", "case", "do", "else",
                                               "in", "of", "new", "delete", "void", "throw",
                                               "=>", "&&", "||", "??", "==", "===", "!=",
                                               "!==", "yield", "await"}
TYPE_WORDS = {"void", "string", "number", "boolean", "any", "unknown", "never",
              "bigint", "symbol", "object"}
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
NUMBER = re.compile(r"\d[\w.]*")


def tokens(text: str) -> list[tuple[str, int]]:
    """(token, line) with strings, comments, template text and regex
    literals left out; `${` opens a brace like any block."""
    out: list[tuple[str, int]] = []
    i, n, line = 0, len(text), 1
    tmpl: list[int] = []  # brace depth at each open `${`
    depth = 0

    def skip_template(j: int) -> int:
        """From inside a template literal to its end or its next `${`."""
        nonlocal line, depth
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "\n":
                line += 1
            if c == "`":
                return j + 1
            if c == "$" and j + 1 < n and text[j + 1] == "{":
                depth += 1
                tmpl.append(depth)
                out.append(("{", line))
                return j + 2
            j += 1
        return j

    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += text.count("\n", i, j)
            i = j
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            i = j + 1 if j < n and text[j] == c else j
            out.append(("'s'", line))
        elif c == "`":
            out.append(("'s'", line))
            i = skip_template(i + 1)
        elif c == "/" and (not out or (out[-1][0] in REGEX_BEFORE and out[-1][0] != "<")):
            j, cls = i + 1, False
            while j < n and text[j] != "\n":
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "[":
                    cls = True
                elif text[j] == "]":
                    cls = False
                elif text[j] == "/" and not cls:
                    break
                j += 1
            if j >= n or text[j] != "/":  # no closing slash on the line: a division
                out.append(("/", line))
                i += 1
                continue
            i = j + 1
            while i < n and text[i].isalpha():
                i += 1
            out.append(("/re/", line))
        elif m := IDENT.match(text, i):
            out.append((m.group(), line))
            i = m.end()
        elif m := NUMBER.match(text, i):
            out.append(("0", line))
            i = m.end()
        else:
            op = next((o for o in OPS if text.startswith(o, i)), c)
            if op == "{":
                depth += 1
            elif op == "}":
                if tmpl and tmpl[-1] == depth:
                    tmpl.pop()
                    depth -= 1
                    out.append(("}", line))
                    i = skip_template(i + 1)
                    continue
                depth -= 1
            out.append((op, line))
            i += len(op)
    return out


def _head_before(toks: list, k: int) -> str | None:
    """The name before the `(` at k, skipping a generic `<...>`."""
    j = k - 1
    if j >= 0 and toks[j][0] == ">":
        lvl = 0
        while j >= 0:
            t = toks[j][0]
            lvl += t == ">"
            lvl -= t == "<"
            j -= 1
            if lvl == 0:
                break
    return toks[j][0] if j >= 0 else None


def functions(text: str):
    """One dict per function: q (name), line, cc, sloc, key."""
    toks = tokens(text)
    lines = text.splitlines()
    close_of: dict[int, int] = {}
    back: dict[int, int] = {}
    stack = []
    for k, (t, _) in enumerate(toks):
        if t in "({[":
            stack.append(k)
        elif t in ")}]" and stack:
            o = stack.pop()
            close_of[o], back[k] = k, o
    # each function: the token its span starts at (its parameter list,
    # where defaults live) -> (name, line, last token of its body)
    spans: dict[int, tuple] = {}

    def params_before_arrow(a: int) -> int:
        """The `(` of an arrow's parameters, or its single parameter."""
        j = a - 1
        while j >= 0 and toks[j][0] not in (")",) and IDENT.fullmatch(toks[j][0]) is None:
            j -= 1
        if j >= 0 and toks[j][0] == ")" and j in back:
            return back[j]
        return max(j, 0)

    for k, (t, ln) in enumerate(toks):
        if t != "{":
            continue
        prev = toks[k - 1][0] if k >= 1 else ""
        if prev == "=>":
            st = params_before_arrow(k - 1)
            spans[st] = (_arrow_name(toks, k - 1), toks[k - 1][1], close_of.get(k, len(toks) - 1))
            continue
        # `) [: Type] {` — walk back over a return type to the `)`
        lvl, j = 0, k - 1
        while j >= 0:
            t2 = toks[j][0]
            if t2 == ")" and lvl == 0:
                break
            if t2 in ";{}=" and lvl == 0:
                j = -1
                break
            lvl += t2 in (">", "]")
            lvl -= t2 in ("<", "[")
            j -= 1
        if j < 0 or toks[j + 1][0] not in ("{", ":"):  # `) {` or `): Type {` only
            continue
        o = back.get(j)
        if o is None or toks[o][0] != "(":
            continue
        head = _head_before(toks, o)
        if head == "function" or (head and IDENT.fullmatch(head) and head not in CONTROL):
            name = head if head != "function" else _arrow_name(toks, o - 1)
            spans[o] = (name, toks[o][1], close_of.get(k, len(toks) - 1))
    # expression-bodied arrows: the body ends at the `,` `;` or unmatched
    # closing bracket at its own depth
    for k, (t, ln) in enumerate(toks):
        if t != "=>" or k + 1 >= len(toks) or toks[k + 1][0] == "{":
            continue
        lvl, e = 0, k + 1
        while e < len(toks):
            t2 = toks[e][0]
            if t2 in "([{":
                lvl += 1
            elif t2 in ")]}":
                if lvl == 0:
                    break
                lvl -= 1
            elif t2 in (",", ";") and lvl == 0:
                break
            e += 1
        nxt = toks[k + 1][0]
        after = toks[k + 2][0] if k + 2 < len(toks) else ""
        if nxt in TYPE_WORDS or (nxt[:1].isupper() and after in ("<", "[", ",", ";", ")", "}", "|")):
            continue  # `(n: number) => void` is a type, not a function
        st = params_before_arrow(k)
        spans.setdefault(st, (_arrow_name(toks, k), toks[st][1], e))
    out = []
    for st, (name, ln, end) in sorted(spans.items()):
        cc, skip_to, opener = 1, -1, []
        for x in range(st + 1, end):
            if x <= skip_to:
                continue
            if x in spans:
                skip_to = spans[x][2]
                continue
            t = toks[x][0]
            if t in DECISION_WORDS or t in DECISION_OPS or t == "?.":
                cc += 1
            elif t == "?" and x + 1 < end and toks[x + 1][0] not in (":", ")", ",", "?", "="):
                cc += 1
            elif t == "=" and _in_pattern(toks, x, back, st):
                cc += 1  # a default value, in the parameters or a destructuring
        last = toks[end][1] if end < len(toks) else ln
        body = lines[ln - 1:last]
        sloc = sum(1 for l in body if l.strip() and not l.strip().startswith(("//", "*", "/*")))
        key = hashlib.blake2b("\n".join(body).strip().encode(), digest_size=16).hexdigest()
        out.append({"q": name or f"<anonymous>@{ln}", "line": ln, "cc": cc,
                    "sloc": sloc, "key": key})
    return out


def _in_pattern(toks: list, x: int, back: dict, st: int) -> bool:
    """Is the `=` at x a default inside a parameter list or a
    destructuring pattern (`(a = 1)`, `{ a = 1 }`, `[a = 1]`)?"""
    lvl, j = 0, x - 1
    while j >= st:
        t = toks[j][0]
        if t in (")", "]", "}"):
            lvl += 1
        elif t in ("(", "[", "{"):
            if lvl == 0:
                before = toks[j - 1][0] if j >= 1 else ""
                if j == st and t == "(":
                    return True  # the function's own parameters
                if t in ("{", "[") and before in ("const", "let", "var", "(", ","):
                    return True
                return before in ("const", "let", "var") if t != "(" else False
            lvl -= 1
        elif lvl == 0 and t in (";",):
            return False
        j -= 1
    return False


def _arrow_name(toks: list, j: int) -> str | None:
    """`const name = (...) =>`, `name: (...) =>`, `name = async x =>`."""
    k = j - 1
    lvl = 0
    while k >= 0:
        t = toks[k][0]
        if t in (")", "]", ">"):
            lvl += 1
        elif t in ("(", "[", "<"):
            lvl -= 1
            if lvl < 0:
                return None
        elif lvl == 0 and t in ("=", ":"):
            name = toks[k - 1][0] if k >= 1 else None
            return name if name and IDENT.fullmatch(name) else None
        elif lvl == 0 and t in (";", "{", "}", ","):
            return None
        k -= 1
    return None
