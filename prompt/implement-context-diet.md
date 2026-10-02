# Prompt: add the context-diet hook to your own project

Copy everything below the line into Claude Code (or another coding agent that supports
Claude Code hooks), started in **your project's root folder**, with this repository
cloned somewhere on the same machine. Replace the one placeholder first:

- `<PATH-TO-THIS-REPO>`: where you cloned this repository

---

I want to cut the tokens my coding agent spends re-reading large tool outputs. A reference
implementation is in `<PATH-TO-THIS-REPO>`. Install it for the project in my current folder,
prove it works, and report back. Work in this order and stop where I say stop.

**Ground rules**
- Do not change any file in my project's source code. This is agent tooling only.
- Before editing `~/.claude/settings.json`, copy it to `~/.claude/settings.json.bak` and show me
  the hooks section you plan to write. Wait for my "yes".
- Never send output that looks like a password, key or token to a second model. The script
  already refuses these; do not weaken that check.
- If anything below fails twice, stop and tell me what failed, with the exact error.

**Step 1. Read the reference**
1. Read `<PATH-TO-THIS-REPO>/README.md`, then `docs/01-source-claude-context-diet.md`,
   `docs/02-rtk-savings.md` and `docs/03-trial-on-acme.md`.
2. Read `implementation/hooks/compress-tool-output.py` and `install-compress-hook.py` in full.
   Ignore `reference/original-hook/`; it is the unreviewed original, kept for comparison.
3. Tell me in five bullets or fewer what the hook does, what it never compresses, and what it
   costs per call.

**Step 2. Check this machine**
1. Report my OS, `python --version` / `python3 --version`, and `claude --version`.
2. Run `claude --help` and confirm these flags exist: `--effort`, `--json-schema`, `--tools`,
   `--strict-mcp-config`, `--setting-sources`, `--no-session-persistence`, `--system-prompt`,
   `--output-format`. If any is missing, stop: my Claude Code is too old.
3. On Windows, check whether `claude` resolves to a `.cmd` launcher; the script handles that
   by calling the `claude.exe` behind it. Confirm that file exists.
4. Check whether `rtk` is installed (`rtk --version`) and whether `~/.claude/settings.json`
   already has a `rtk hook claude` entry.

**Step 3. Copy and point it at my project**
1. Copy the three files from `implementation/hooks/` into `.claude/hooks/context-diet/` in my
   project.
2. The script finds its scope from where it sits (`WORKSPACE = parents[3]`). Change that one
   line so `WORKSPACE` is my project's root folder, resolved from the script's location.
   Compression must only happen in sessions started inside my project.
3. Update the test file's sample paths to match, then run
   `python .claude/hooks/context-diet/test_compress_tool_output.py`. All tests must pass
   before you go on.

**Step 4. One real call, before wiring anything**
1. Find a search in my project whose output is between 3,500 and 50,000 tokens (characters ÷ 4)
   and contains no secret-looking words: for example `grep -rn "def \|function " src`.
2. Feed it to the script as a PostToolUse event on stdin (`compress-tool-output.py post`) and
   show me: tokens before, tokens after, seconds taken, and the first lines of the summary.
3. Check two facts in the summary against the raw output yourself (a file name and a line
   number). Tell me if either is wrong. If one is, stop.

**Step 5. Wire it (after my "yes")**
1. Run the installer from its new location: `python` on Windows, `python3` on Mac and Linux.
   It adds the PostToolUse entry and, if rtk is installed, puts the script in front of rtk so
   rtk keeps handling every command the compressor does not own.
2. If rtk is not installed, the PreToolUse entry does nothing; say so.
3. Show me the final hooks section and confirm the file is valid JSON.

**Step 6. Prove it in a fresh session**
1. Start a new non-interactive session in my project, for example:
   `claude -p "Run this Bash command once: <the search from step 4>. Reply with the first line of the tool result." --allowedTools "Bash(grep:*)"`
2. Show me the new line in `~/.cache/compress-hook/ledger.jsonl`. It must say `"compressed"`.
3. Run `compress-tool-output.py report` and show the totals.

**Step 7. Report**
Report as a short list: what was installed and where, the measured numbers from steps 4 and 6,
what was not proved (real savings over days of work, summary accuracy beyond the two facts you
checked), and the one command that turns it off:
`python .claude/hooks/context-diet/install-compress-hook.py --uninstall`.

**Things to warn me about in the report**
- Each compression is an extra model call: about 10 seconds, and it counts against my plan.
- With rtk installed, small searches inside my project no longer get rtk's shortening.
- rtk may print "No hook installed" once a day, because its own line in settings is now
  wrapped. Running `rtk init -g` would undo the arrangement.
- The hook only takes effect in sessions started after it is installed.
