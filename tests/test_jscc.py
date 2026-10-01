"""TypeScript/JavaScript cyclomatic complexity by tokens (runtime/jscc.py,
owner request 2026-10-01): the front counts in complexity and structural
erosion. Calibrated on ESLint 10's `complexity` rule over 4,836 client
functions: 98% exact, 99.6-99.9% on the same side of CC 10."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import erosion  # noqa: E402
import jscc  # noqa: E402


def cc(src: str) -> dict:
    return {f["q"]: f["cc"] for f in jscc.functions(src)}


class Counting(unittest.TestCase):
    def test_each_decision_eslint_counts(self):
        # ESLint 10 `complexity`, probed one construct per function
        src = """
function base() { return 1 }
function optchain(a: any) { return a?.b?.c }
function defparam(a = 1, b = 2) { return a + b }
function destr({ x = 1, y = 2 }: any) { return x + y }
function nullish(a: any) { return a ?? 1 }
function optcall(a: any) { return a?.() }
function tern(a: any) { return a ? 1 : 2 }
function loops(xs: any[]) { for (const x of xs) { while (x) { if (x && y || z) { break } } } }
function sw(k: string) { switch (k) { case "a": return 1; case "b": return 2; default: return 0 } }
function tc() { try { go() } catch (e) { return 1 } }
"""
        self.assertEqual(cc(src), {"base": 1, "optchain": 3, "defparam": 3, "destr": 3,
                                   "nullish": 2, "optcall": 2, "tern": 2, "loops": 6,
                                   "sw": 3, "tc": 2})

    def test_nested_functions_count_on_their_own(self):
        src = """
export function Page() {
  const onClick = () => a && b
  const load = async (id: string) => { if (id) { return 1 } }
  return <button onClick={() => x || y}>go</button>
}
"""
        got = cc(src)
        self.assertEqual(got["Page"], 1)
        self.assertEqual(got["onClick"], 2)
        self.assertEqual(got["load"], 2)

    def test_methods_getters_and_generics(self):
        src = """
class K<T> extends Base {
  constructor(private x: T) { super() }
  async load<U>(id: string): Promise<U> { return id ? a : b }
  get name() { return this.x || "n" }
}
"""
        self.assertEqual(cc(src), {"constructor": 1, "load": 2, "name": 2})

    def test_types_strings_and_regex_are_not_code(self):
        src = """
type P = { a?: string; on: (n?: number) => void; run: () => Promise<void> }
function f(p: P, s = "if (a && b) {"): string {
  const re = /a&&b|c\\/d[/]/g
  return `x${p.a ? "y" : "z"}`  // && || in a comment
}
"""
        self.assertEqual(cc(src), {"f": 3})  # default + template ternary

    def test_no_semicolons_do_not_make_functions(self):
        src = """
export default function Detail() {
  const { user } = useAuth()
  const { data } = useAgent(id)
  return data ? user : null
}
"""
        self.assertEqual(cc(src), {"Detail": 2})

    def test_jsx_closing_tags_keep_line_numbers(self):
        src = "function A() {\n  return (\n    <B>\n      <C>x</C>\n    </B>\n  )\n}\n\nfunction D() { return 1 }\n"
        lines = {f["q"]: f["line"] for f in jscc.functions(src)}
        self.assertEqual(lines, {"A": 1, "D": 9})


class InStructuralErosion(unittest.TestCase):
    def test_typescript_counts_and_declarations_and_tests_do_not(self):
        heavy = "function h(a) {\n" + "".join(f"  if (a == {i}) {{ a++ }}\n" for i in range(12)) + "}\n"
        light = "function l(a) {\n  return a\n}\n"
        r = erosion.structural_erosion({"web/a.ts": heavy, "web/b.tsx": light,
                                        "web/types.d.ts": heavy.replace("h(", "d("),
                                        "web/a.test.ts": heavy.replace("h(", "t(")})
        self.assertEqual(r["functions"], 2)
        self.assertEqual(r["complex"], 1)
        self.assertGreater(r["erosion"], 0.5)


if __name__ == "__main__":
    unittest.main()
