"""Tests for compress-tool-output.py. The Sonnet helper is replaced by a stub: no claude call.

Run: python .agents/hooks/shared/test_compress_tool_output.py
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "compress_tool_output", os.path.join(os.path.dirname(__file__), "compress-tool-output.py"))
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

WS = str(hook.WORKSPACE / "Projects" / "app")
BIG = "\n".join(f"src/file{i}.py:{i}: def handler_{i}(event): return process(event)" for i in range(800))
FACTS = {"facts": ["800 matches of def handler_N in src/file0.py..src/file799.py"], "unknowns": []}


def post(command, stdout=BIG, cwd=WS, **resp):
    return {"hook_event_name": "PostToolUse", "cwd": cwd, "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False, "isImage": False, **resp}}


class PostToolUseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(hook, "ARCHIVE", Path(self.tmp.name) / "raw"),
                        mock.patch.object(hook, "LEDGER", Path(self.tmp.name) / "ledger.jsonl"),
                        mock.patch.object(hook, "summarize", return_value=FACTS)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_large_grep_is_replaced_with_same_shape(self):
        out = hook.handle_post(post("grep -rn handler src"))
        new = out["hookSpecificOutput"]["updatedToolOutput"]
        self.assertEqual(set(new), {"stdout", "stderr", "interrupted", "isImage"})
        self.assertTrue(new["stdout"].startswith("[compressed by Sonnet 5.5: ~"))
        self.assertIn("800 matches", new["stdout"])
        raw_path = new["stdout"].split("full output: ")[1].split("]")[0]
        self.assertEqual(Path(raw_path).read_text(encoding="utf-8"), BIG)
        self.assertEqual(json.loads(Path(hook.LEDGER).read_text().splitlines()[0])["result"], "compressed")

    def test_cd_prefix_and_rtk_prefix_still_match(self):
        self.assertIsNotNone(hook.handle_post(post("cd Projects/app && grep -rn handler src")))
        self.assertIsNotNone(hook.handle_post(post("rtk grep -rn handler src")))

    def test_mcp_result_keeps_content_shape(self):
        ev = {"cwd": WS, "tool_name": "mcp__search__find", "tool_input": {},
              "tool_response": {"content": [{"type": "text", "text": BIG}]}}
        new = hook.handle_post(ev)["hookSpecificOutput"]["updatedToolOutput"]
        self.assertEqual(new["content"][0]["type"], "text")

    def test_left_alone(self):
        cases = {
            "outside workspace": post("grep -rn x .", cwd=r"C:\Projects\Initech\infra"),
            "exact read": post("cat big.log"),
            "small output": post("grep -rn x .", stdout="a.py:1: x"),
            "stderr present": post("grep -rn x .", stderr="grep: dir: Permission denied"),
            "looks like a secret": post("grep -rn x .", stdout=BIG + "\nAWS_SECRET_ACCESS_KEY=abc"),
            "interrupted": post("grep -rn x .", interrupted=True),
        }
        for name, ev in cases.items():
            with self.subTest(name):
                self.assertIsNone(hook.handle_post(ev))

    def test_summary_not_small_enough_keeps_original(self):
        with mock.patch.object(hook, "summarize", return_value={"facts": [BIG[:20000]], "unknowns": []}):
            self.assertIsNone(hook.handle_post(post("grep -rn handler src")))

    def test_helper_failure_keeps_original(self):
        with mock.patch.object(hook, "summarize", side_effect=RuntimeError("quota")):
            self.assertIsNone(hook.handle_post(post("grep -rn handler src")))


class PreToolUseTest(unittest.TestCase):
    """rtk is secondary: inside the workspace it does not touch commands the compressor owns."""

    def test_compressor_commands_skip_rtk(self):
        for cmd in ["grep -rn x .", "rg foo", "git log --oneline", "cd a && git status", "npm test"]:
            with self.subTest(cmd):
                self.assertFalse(hook.rtk_should_run({"cwd": WS, "tool_input": {"command": cmd}}))

    def test_other_commands_and_outside_workspace_keep_rtk(self):
        self.assertTrue(hook.rtk_should_run({"cwd": WS, "tool_input": {"command": "ls -la"}}))
        self.assertTrue(hook.rtk_should_run({"cwd": r"C:\Projects\Initech", "tool_input": {"command": "grep -rn x ."}}))


class FindClaudeTest(unittest.TestCase):
    def test_windows_cmd_launcher_resolves_to_exe(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
            exe.parent.mkdir(parents=True)
            exe.write_text("")
            with mock.patch.object(hook.shutil, "which", return_value=str(Path(d, "claude.CMD"))):
                self.assertEqual(hook.find_claude(), str(exe))


if __name__ == "__main__":
    unittest.main()
