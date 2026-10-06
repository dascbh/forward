"""USE-16 (owner's UX inspection, 2026-10-05): spec prose living in the
interface. uiprose.py lists explanatory UI sentences; the rule lives in
the catalog, the design chain and the planner."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

import quietgit  # noqa: E402,F401
import uiprose  # noqa: E402
from prose import ProseTestCase  # noqa: E402

SCREEN = """export function Acervo({ empresa }) {
  return (<div>
    <button>Enviar contratos</button>
    <p>Os contratos enviados ficam na empresa do seletor no alto da tela (a do cabeçalho).</p>
    <span className="help">Escolha a empresa.</span>
    <Field label="Nome do contrato" />
    {erro && <Alert>Falha ao enviar os arquivos — tente novamente em alguns instantes.</Alert>}
  </div>);
}
"""


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)


class TestSentences(unittest.TestCase):
    def test_sentences_are_found_labels_and_code_are_not(self):
        found = uiprose.sentences(SCREEN)
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].startswith("Os contratos enviados ficam na empresa"))
        self.assertNotIn("Enviar contratos", " ".join(found))
        self.assertNotIn("className", " ".join(found))

    def test_changed_lists_only_what_the_branch_adds(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git(root, "init", "-q", "-b", "main")
            git(root, "config", "user.email", "t@example.com")
            git(root, "config", "user.name", "t")
            (root / "src").mkdir()
            (root / "src" / "Old.tsx").write_text(SCREEN)
            git(root, "add", "-A")
            git(root, "commit", "-qm", "old")
            git(root, "checkout", "-qb", "feature")
            (root / "src" / "New.tsx").write_text(
                "<p>O sistema grava a análise e recalcula o resumo a cada nova versão do texto.</p>\n")
            r = uiprose.report(root, changed=True)
            self.assertEqual(list(r["files"]), ["src/New.tsx"], "untracked: still building")
            git(root, "add", "-A")
            git(root, "commit", "-qm", "new")
            r = uiprose.report(root, changed=True)
            self.assertEqual(list(r["files"]), ["src/New.tsx"], "committed on the branch")
            self.assertEqual(r["sentences"], 1)
            self.assertEqual(uiprose.report(root, changed=False)["sentences"], 3)


class TestRule(ProseTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_the_rule_reaches_catalog_design_and_planner(self):
        for rel in ("spec/dimensions/quality-attributes.toml",
                    ".fde/spec/dimensions/quality-attributes.toml"):
            self.assertIn("USE-16 the screen speaks the user's next action, never the spec",
                          self.read(rel))
        design = self.read("skills/fde-design/SKILL.md")
        self.assertIn("Real means the\nuser's words for the next action, never the spec's (USE-16)",
                      design)
        self.assertIn("python3 bin/fde/uiprose.py --changed", design)
        self.assertIn("never by a sentence on the screen that says\n  it holds (USE-16)",
                      self.read("agents/fde-spec.md"))


if __name__ == "__main__":
    unittest.main()
