"""Tests for rtk-savings.py against a throwaway rtk history database.

Run: python3 -m unittest mcp/tools/test_rtk_savings.py
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "rtk-savings.py")
_spec = importlib.util.spec_from_file_location("rtk_savings", SCRIPT)
rtk = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rtk
_spec.loader.exec_module(rtk)

WS = r"C:\Projects\AcmeProducts\Projects\app"
OTHER = r"C:\Projects\Other"

# rtk_cmd, original_cmd, input, output, project_path
ROWS = [
    ("rtk grep -rn x src", "grep -rn x src", 10_000, 500, WS),
    ("rtk grep -rn y package.json", "grep -rn y package.json", 40_000_000, 4_000, WS),  # bogus outlier
    ("rtk read a.md", "cat a.md", 2_000, 200, OTHER),
    ("rtk git status", "git status", 300, 100, WS),
    ("rtk git show HEAD:big.db", "git show HEAD:big.db", 9_000, 9_000, WS),
    ("rtk cargo test", "cargo test", 5_000, 100, WS),
    ("rtk proxy git log", "git log", 700, 700, WS),
    ("rtk fallback: diff a b", "diff a b", 0, 0, WS),
    ("rtk fallback: echo hi", "echo hi", 0, 0, OTHER),
]


def make_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE commands (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, original_cmd TEXT NOT NULL,"
        " rtk_cmd TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,"
        " saved_tokens INTEGER NOT NULL, savings_pct REAL NOT NULL, exec_time_ms INTEGER DEFAULT 0,"
        " project_path TEXT DEFAULT '')"
    )
    for n, (cmd, orig, i, o, p) in enumerate(ROWS):
        con.execute(
            "INSERT INTO commands (timestamp, original_cmd, rtk_cmd, input_tokens, output_tokens, saved_tokens,"
            " savings_pct, project_path) VALUES (?,?,?,?,?,?,?,?)",
            (f"2026-09-{n + 1:02d}T00:00:00+00:00", orig, cmd, i, o, i - o, 0.0, p),
        )
    con.commit()
    con.close()


class RtkSavingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "history.db"
        make_db(self.db)
        self.report = rtk.build_report(rtk.load_rows(self.db), workspace="AcmeProducts")

    def tearDown(self):
        self.tmp.cleanup()

    def test_categories(self):
        self.assertEqual(rtk.category("rtk git status"), "git")
        self.assertEqual(rtk.category("rtk cargo test"), "Test and build logs")
        self.assertEqual(rtk.category("rtk fallback: diff a b"), rtk.FALLBACK)
        self.assertEqual(rtk.category("rtk:toml terraform plan"), "Cloud and infra")

    def test_outlier_grep_left_out_of_clean_totals(self):
        whole = self.report["scopes"]["all"]
        self.assertEqual(whole["cats"]["grep / rg"], [1, 10_000, 500])
        self.assertEqual(len(self.report["outliers"]), 1)
        self.assertEqual(self.report["rtk_headline"]["input"], 40_000_000 + 10_000 + 2_000 + 300 + 9_000 + 5_000 + 700)

    def test_workspace_scope_and_fallback_count(self):
        ws = self.report["scopes"]["ws"]
        self.assertNotIn("File reads", ws["cats"])  # the read ran outside the workspace
        self.assertEqual(ws["fallback"], 1)
        self.assertEqual(ws["runs"], 6)  # 7 rows in the workspace, minus the bogus grep
        self.assertEqual(self.report["scopes"]["all"]["fallback"], 2)

    def test_biggest_run_per_category(self):
        self.assertEqual(self.report["scopes"]["ws"]["big"]["git"][0], 9_000)

    def test_cli_writes_html_and_json(self):
        out = Path(self.tmp.name) / "r.html"
        js = Path(self.tmp.name) / "r.json"
        res = subprocess.run(
            [sys.executable, SCRIPT, "--db", str(self.db), "--html", str(out), "--json", str(js)],
            capture_output=True, text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("grep / rg", res.stdout)
        page = out.read_text(encoding="utf-8")
        self.assertIn("<title>RTK Token Savings</title>", page)
        self.assertNotIn("__DATA__", page)
        self.assertIn("scopes", json.loads(js.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
