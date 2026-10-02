#!/usr/bin/env python3
"""Wire compress-tool-output.py into this machine's ~/.claude/settings.json. Run once per laptop
(Windows and Mac), and again after the workspace folder moves.

    python  .agents/hooks/shared/install-compress-hook.py              # Windows
    python3 .agents/hooks/shared/install-compress-hook.py              # Mac
    ... install-compress-hook.py --dry-run     show the hooks section it would write
    ... install-compress-hook.py --uninstall   put plain `rtk hook claude` back, drop compression

It swaps the PreToolUse `rtk hook claude` entry for `compress-tool-output.py pre` (which still
calls rtk for everything the compressor does not own) and adds the PostToolUse entry. Uses the
absolute path of this checkout and `python` on Windows, `python3` elsewhere. Running it twice
changes nothing. The old file is kept as settings.json.bak.
"""
import json
import pathlib
import shutil
import sys

SCRIPT = pathlib.Path(__file__).resolve().parent / "compress-tool-output.py"
SETTINGS = pathlib.Path.home() / ".claude" / "settings.json"
PY = "python" if sys.platform == "win32" else "python3"
RTK = "rtk hook claude"


def ours(entry):
    return any("compress-tool-output.py" in h.get("command", "") or h.get("command") == RTK
               for h in entry.get("hooks", []))


def command(mode):
    return f'{PY} "{SCRIPT.as_posix()}" {mode}'


def apply(settings, uninstall=False):
    hooks = settings.setdefault("hooks", {})
    pre = [e for e in hooks.get("PreToolUse", []) if not ours(e)]
    post = [e for e in hooks.get("PostToolUse", []) if not ours(e)]
    if uninstall:
        pre.insert(0, {"matcher": "Bash", "hooks": [{"type": "command", "command": RTK}]})
    else:
        pre.insert(0, {"matcher": "Bash", "hooks": [{"type": "command", "command": command("pre " + RTK)}]})
        post.insert(0, {"matcher": "Bash|mcp__.*",
                        "hooks": [{"type": "command", "command": command("post"), "timeout": 120}]})
    hooks["PreToolUse"] = pre
    if post:
        hooks["PostToolUse"] = post
    else:
        hooks.pop("PostToolUse", None)
    return settings


def main(args):
    settings = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    new = apply(settings, uninstall="--uninstall" in args)
    if "--dry-run" in args:
        print(json.dumps(new["hooks"], indent=2))
        return
    if SETTINGS.exists():
        shutil.copy2(SETTINGS, SETTINGS.with_suffix(".json.bak"))
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
    print(("Removed" if "--uninstall" in args else "Installed") + f" in {SETTINGS}. Start a new Claude session.")


if __name__ == "__main__":
    main(sys.argv[1:])
