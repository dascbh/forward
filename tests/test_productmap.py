"""The product map (runtime/productmap.py, owner request 2026-09-30),
generated from a synthetic project: screens, API clients, a route table,
guards and business rules with their messages, events, SQL, triggers."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import productmap  # noqa: E402

FILES = {
    "web/src/Routes.tsx": """\
        import InvoicesPage from "./pages/billing/InvoicesPage";
        import InvoicePage from "./pages/billing/InvoicePage";
        export const R = () => (
          <Routes>
            <Route path="/billing" element={<Layout nav={NAV} title="Billing" />}>
              <Route element={<Gate />}>
                <Route index element={<InvoicesPage />} />
                <Route path="invoices/:invoiceId" element={<InvoicePage />} />
              </Route>
            </Route>
          </Routes>
        );
        """,
    "web/src/pages/billing/billingApi.ts": """\
        const id = encodeURIComponent;
        const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });
        const base = (invoiceId: string) => `/billing/invoices/${id(invoiceId)}`;
        async function listLines(invoiceId: string, cancel: () => boolean = () => false): Promise<Line[]> {
          return pages(`${base(invoiceId)}/lines`, {}, cancel);
        }
        export const billingApi = {
          listInvoices: () => call("/billing/invoices", {}, parse),
          getInvoice: (invoiceId: string) => call(base(invoiceId), {}, parse),
          /** closes the invoice */
          closeInvoice: (invoiceId: string) =>
            call(`${base(invoiceId)}/close`, json("POST", {}), parse),
          listLines,
        };
        """,
    "web/src/pages/billing/InvoicesPage.tsx": """\
        import { billingApi } from "./billingApi";
        export default function InvoicesPage() { billingApi.listInvoices(); return null; }
        """,
    "web/src/pages/billing/InvoicePage.tsx": """\
        import { billingApi } from "./billingApi";
        import LinesTab from "./LinesTab";
        export default function InvoicePage() {
          billingApi.getInvoice("x"); billingApi.closeInvoice("x");
          return <LinesTab />;
        }
        """,
    "web/src/pages/billing/LinesTab.tsx": """\
        import { billingApi } from "./billingApi";
        export default function LinesTab() { billingApi.listLines("x"); return null; }
        """,
    "api/shared/http.py": """\
        MESSAGES = {
            "INVOICE_CLOSED": (409, "This invoice is closed."),
            "FORBIDDEN": (403, "You cannot see this invoice."),
        }
        BY_KEY = {("NO_LINES", None): (409, "MSG_NO_LINES")}
        def error(code):
            return Exception(code)
        """,
    "api/shared/vocab.py": 'MSG_NO_LINES = "An invoice needs at least one line."\n',
    "api/shared/access.py": """\
        from http import error
        def require_member(db, invoice_id):
            if not db:
                raise deny(invoice_id, "FORBIDDEN")
            return db.query("SELECT 1 FROM app.invoice_member WHERE invoice_id = :i")
        def deny(ref, code):
            return error(code)
        """,
    "api/shared/events.py": "def emit(name, **kw):\n    print(name)\n",
    "api/billing/handler.py": """\
        import access
        from http import error
        from events import emit
        LINES = "SELECT l.id FROM app.invoice_line l WHERE l.invoice_id = :i"
        SQL_CLOSE = f\"\"\"-- billing.close
            UPDATE app.invoice SET status = 'CLOSED', closed_at = now() WHERE id = :i
              AND EXISTS ({LINES})\"\"\"
        def _list(db, params):
            return db.query("SELECT id, total FROM app.invoice")
        def _get(db, params):
            access.require_member(db, params["invoice_id"])
            return db.query("SELECT * FROM app.invoice WHERE id = :i")
        def _close(db, params):
            access.require_member(db, params["invoice_id"])
            if params.get("closed"):
                raise error("INVOICE_CLOSED")
            if not params.get("lines"):
                raise error("NO_LINES")
            db.execute(SQL_CLOSE)
            db.execute("INSERT INTO app.invoice_audit (invoice_id, action) VALUES (:i, 'close')")
            emit("INVOICE_CLOSED_EVT", invoice=params["invoice_id"])
        def _lines(db, params):
            return db.query(LINES)
        P = "/billing/invoices/{invoice_id}"
        ROUTES = {
            "/billing/invoices": {"GET": _list},
            P: {"GET": _get},
            P + "/close": {"POST": _close},
            P + "/lines": {"GET": _lines},
            "/billing/export": {"GET": _list},
        }
        """,
    "db/migrations/001.sql": """\
        CREATE FUNCTION app.fn_invoice_history() RETURNS trigger AS $$
        BEGIN INSERT INTO app.invoice_history (invoice_id) VALUES (NEW.id); RETURN NEW; END $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_invoice_history AFTER UPDATE ON app.invoice
          FOR EACH ROW EXECUTE FUNCTION app.fn_invoice_history();
        CREATE FUNCTION app.fn_append_only() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'no'; END $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_audit_append_only BEFORE UPDATE ON app.invoice_audit
          FOR EACH ROW EXECUTE FUNCTION app.fn_append_only();
        """,
}

CONVENTIONS = """\
[frontend]
source_root = "web/src"
routes_file = "web/src/Routes.tsx"
client_glob = "*Api.ts"
path_base_helper = "base"

[backend]
shared_dir = "api/shared"
route_table = "ROUTES"
table_pattern = '(?:app\\.)?(invoice\\w*)\\b'
sql_tag = '--\\s*(billing\\.[\\w.]+)'
migrations_glob = "db/migrations/*.sql"

[rules]
refusal_calls = ["error", "deny"]
guard_prefixes = ["require_"]
protocol_codes = ["NOT_FOUND"]
catalogs = [
  { file = "api/shared/http.py", name = "MESSAGES" },
  { file = "api/shared/http.py", name = "BY_KEY", messages_from = "api/shared/vocab.py" },
]

[events]
emit_calls = ["emit"]

[[feature]]
slug = "billing"
name = "Billing"
route_prefix = "/billing"
feature_dir = "web/src/pages/billing"
handler_glob = "api/billing/handler.py"
"""


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for rel, text in FILES.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(textwrap.dedent(text))
        (self.root / "docs" / "map").mkdir(parents=True)
        (self.root / "docs" / "map" / "conventions.toml").write_text(CONVENTIONS)
        self.conv = productmap.load_conventions(self.root)
        self.feature = self.conv["feature"][0]
        self.g = productmap.Mapper(self.root, self.conv, self.feature).build()

    def has(self, a, rel, b):
        return any(x == a and r == rel and y == b for x, r, y, _ in self.g.edges)


class TestGraph(Fixture):
    def test_screens_from_the_route_tree(self):
        screens = sorted(n for n in self.g.nodes if n.startswith("screen:"))
        self.assertEqual(screens, ["screen:/billing", "screen:/billing/invoices/:invoiceId"])

    def test_every_client_call_reaches_its_handler(self):
        for comp, api, handler in (
                ("component:InvoicesPage", "api:GET /billing/invoices", "handler:handler._list"),
                ("component:InvoicePage", "api:POST /billing/invoices/{invoiceId}/close", "handler:handler._close"),
                ("component:LinesTab", "api:GET /billing/invoices/{invoiceId}/lines", "handler:handler._lines")):
            self.assertTrue(self.has(comp, "calls", api), (comp, api))
            self.assertTrue(self.has(api, "handled_by", handler), (api, handler))
        self.assertFalse([n for n, d in self.g.nodes.items() if d["kind"] == "unresolved"])

    def test_an_operation_no_screen_calls_is_listed(self):
        self.assertTrue(self.g.nodes["api:GET /billing/export"].get("no_screen"))

    def test_rules_guards_and_events(self):
        self.assertTrue(self.has("handler:handler._close", "applies", "guard:access.require_member"))
        self.assertTrue(self.has("guard:access.require_member", "refuses", "rule:FORBIDDEN"))
        self.assertTrue(self.has("handler:handler._close", "refuses", "rule:INVOICE_CLOSED"))
        self.assertEqual(self.g.nodes["rule:INVOICE_CLOSED"]["message"], "This invoice is closed.")
        self.assertEqual(self.g.nodes["rule:NO_LINES"]["message"],
                         "An invoice needs at least one line.")       # through the vocabulary
        self.assertTrue(self.has("handler:handler._close", "emits", "event:INVOICE_CLOSED_EVT"))

    def test_sql_columns_nested_constants_and_triggers(self):
        self.assertTrue(self.has("handler:handler._close", "writes", "column:invoice.status"))
        self.assertTrue(self.has("handler:handler._close", "writes", "column:invoice.closed_at"))
        self.assertTrue(self.has("handler:handler._close", "writes", "column:invoice_audit.action"))
        # LINES is nested inside SQL_CLOSE's f-string
        self.assertTrue(self.has("handler:handler._close", "reads", "table:invoice_line"))
        self.assertTrue(self.has("handler:handler._get", "reads", "table:invoice_member"))
        self.assertTrue(self.has("table:invoice", "fires_into", "table:invoice_history"))
        self.assertTrue(self.has("table:invoice_audit", "protected_by", "trigger:trg_audit_append_only"))


class TestFile(Fixture):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "runtime" / "productmap.py"),
                               "--root", str(self.root), *args], capture_output=True, text=True)

    def test_two_levels_and_the_declared_block_survives(self):
        r = self.run_cli("--write")
        self.assertEqual(r.returncode, 0, r.stderr)
        path = self.root / "docs" / "map" / "billing.md"
        text = path.read_text()
        for heading in ("## Summary", "## By screen", "## Business rules", "## Events",
                        "## Tables", "## Declared by hand", "## Edges"):
            self.assertIn(heading, text)
        self.assertLess(text.index("## By screen"), text.index("## Edges"))
        self.assertIn("| `INVOICE_CLOSED` | 409 | This invoice is closed. |", text)
        text = text.replace(productmap.DECL_BEGIN + "\n",
                            productmap.DECL_BEGIN + "\nThe export is read by the finance team.\n")
        path.write_text(text)
        self.run_cli("--write")
        self.assertIn("The export is read by the finance team.", path.read_text())

    def test_check_fails_when_code_moves(self):
        self.run_cli("--write")
        self.assertEqual(self.run_cli("--check").returncode, 0)
        h = self.root / "api" / "billing" / "handler.py"
        h.write_text(h.read_text().replace('"/billing/export": {"GET": _list},',
                                           '"/billing/export": {"GET": _list, "POST": _close},'))
        r = self.run_cli("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("out of date", r.stdout)

    def test_json_is_nodes_and_edges(self):
        data = json.loads(self.run_cli("--format", "json").stdout)
        self.assertIn("screen:/billing", data["nodes"])
        self.assertIn({"source", "relation", "target", "provenance"}, [set(e) for e in data["edges"]])

    def test_no_conventions_names_the_skill(self):
        (self.root / "docs" / "map" / "conventions.toml").unlink()
        r = self.run_cli()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fde-map skill", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()


class TestSkill(unittest.TestCase):
    def test_the_skill_teaches_conventions_and_measuring(self):
        text = (ROOT / "skills" / "fde-map" / "SKILL.md").read_text()
        self.assertIn("The kernel knows no project.", text)
        self.assertIn("measure before trusting it", text)
        self.assertIn("`fde-map`", (ROOT / "README.md").read_text())
