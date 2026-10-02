# Context-diet hook: trial on AcmeProducts

- **Status:** tried on the Windows laptop, then uninstalled; plain rtk is back
- **Source idea:** [01-source-claude-context-diet.md](01-source-claude-context-diet.md)
- **Code:** [implementation/hooks/](../implementation/hooks/). The copy in use lives in the AcmeProducts workspace at `.agents/hooks/shared/` (not wired today).

## Why it was tried

[rtk/rtk-savings.md](../rtk/rtk-savings.md) showed rtk cutting only about 25% of tool output inside this
folder (3.88M raw → 2.92M sent), and 80% of runs had no rtk filter at all. `rtk gain` claims
95.6%, but six bogus grep rows logged at ~123M tokens make that number wrong.

## What was built

- **PostToolUse hook** (`Bash|mcp__.*`): a search or log output over ~3,500 tokens is sent to
  Sonnet 5.5 (`claude -p`, effort medium, no tools, no hooks) and replaced by a short fact list.
  The raw text is kept in `~/.cache/compress-hook/raw/` and its path is in the summary header.
- **Kept raw:** smaller outputs, file reads (`cat`, `sed`), diffs, errors (any stderr),
  interrupted commands, and anything that looks like a password or key.
- **rtk made secondary:** the PreToolUse entry calls the hook script, which skips rtk for the
  commands the compressor owns (grep, rg, find, fd, git log/status, test and build logs) and
  runs `rtk hook claude` for everything else.
- **Only inside AcmeProducts.** Sessions in any other folder (Initech day-job work) kept plain rtk.
- **Both laptops:** `install-compress-hook.py` writes the wiring into `~/.claude/settings.json`
  with `python` on Windows and `python3` on the Mac. `--uninstall` puts plain rtk back.

### Windows fixes over the original script

- `claude` is an npm `.cmd` launcher on Windows; the hook calls the real `claude.exe` behind it,
  so cmd.exe does not re-parse the prompt and schema arguments.
- Files and the helper's input are read and written as UTF-8.
- An optional `cd dir &&` or `rtk ` in front of a command still matches.

## Results

| Check | Result |
|---|---|
| Tests (helper stubbed) | 9 of 9 pass |
| Real Sonnet call, `grep -rn fn Projects/lighthouse-app` | 3,643 → 550 tokens, 9.4 s |
| Fresh Claude session running the same grep | 3,642 → 449 tokens, 10.4 s; rtk did not rewrite it |
| rtk on other commands (`ls -la`) | unchanged, same output as rtk alone |
| Outside the folder (`C:\Projects\Initech`) | rtk on for every command, nothing compressed |
| Ledger total | 2 outputs, ~7,285 → ~999 tokens (86.3% cut), 0 errors |

## Not proved

- Savings over real daily work. Two runs on one grep are not a week of numbers.
- The Mac. The installer picks `python3` there, but it was never run on the Mac.
- Faithfulness on our outputs. The blind test in the source page was someone else's.

## Costs and side effects seen

- About 10 seconds and one Sonnet call (≈ $0.04 at list price, the source page's figure) per
  compressed output, counted against the Claude plan.
- Small greps inside the folder got no rtk shrinking, because rtk was skipped for them.
- rtk prints "No hook installed" once a day, because it no longer finds its own line in
  settings. `RTK_SUPPRESS_HOOK_WARNING=1` did not silence it in rtk 0.38.
- `rtk init -g` would put rtk back in front and undo the arrangement.
- A shell grep on `mcp/tools` was left raw on purpose: `secret-scan.py` contains the word
  "secret", which the hook treats as a possible credential.

## To try it again

```
python  .agents/hooks/shared/install-compress-hook.py    # Windows
python3 .agents/hooks/shared/install-compress-hook.py    # Mac
python  .agents/hooks/shared/compress-tool-output.py report
```

Run it for a week, then compare `report` against `python mcp/tools/rtk-savings.py --since <start>`.
