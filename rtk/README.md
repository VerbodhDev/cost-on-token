# rtk (Rust Token Killer)

- **Project:** https://github.com/rtk-ai/rtk (Apache 2.0, a single Rust binary)
- **Our measurement:** [rtk-savings.md](rtk-savings.md), made with [tool/rtk-savings.py](tool/rtk-savings.py)
- **The alternative we tried:** the context-diet hook, in [../docs/](../docs/)

## What it is

rtk is a command-line proxy that shortens shell output before the agent reads it. Its README
calls it a "CLI proxy that reduces LLM token consumption by 60-90% on common dev commands".

- `rtk init -g` adds a PreToolUse hook to Claude Code. The hook rewrites each Bash command to its
  rtk version, for example `git status` → `rtk git status`.
- Each supported command has its own filter: grouping, truncation, deduplication. Commands with
  no filter run unchanged.
- Its README also says bash output is only one part of the tokens an agent uses, so the overall
  saving is smaller than the per-command figure. It ships no tokenizer, so counts are estimates.

Install: `brew install rtk`, `winget install rtk-ai.rtk`, or the install script in its README.
Then `rtk init -g` and restart Claude Code.

## rtk compared with the context-diet hook

| | rtk | Context-diet hook |
|---|---|---|
| How it cuts | fixed filters per command, written in Rust | a second model (Sonnet 5.5) rewrites the output as a short fact list |
| Hook point | PreToolUse: rewrites the command before it runs | PostToolUse: replaces the result after it runs |
| What it covers | shell commands it has a filter for | large shell search and log output, and MCP tool results (code search, docs, web) |
| What it skips | commands with no filter (80% of runs in our folder) | outputs under ~3,500 tokens, file reads, diffs, errors, anything secret-looking |
| Time added | none noticeable | about 10 s per compressed output |
| Money | free | one model call per compressed output, ≈ $0.04 at list price (source page's figure) |
| Can it drop or bend facts? | no, it only cuts lines | yes, a summary can miss a fact; the raw output is kept on disk to check |
| Claimed cut | 60-90% on common commands | 89.9% on tool output (source page, one developer's week) |
| **Measured by us** | **24.8%** in our project folder, 77.9% across the laptop | **86.3%** on 2 real greps, ~7,285 → ~999 tokens |
| Proven over real work | yes, about three months of history | no, two runs only |

### What the comparison means

- **rtk is cheap and safe, but did little where it mattered.** In our project folder most of the
  token weight was git output and file reads, which it barely cut, and most runs had no filter.
- **`rtk gain` overstates it.** It reported 95.6%; six bogus grep rows made up about 123M of its
  154M raw tokens. See [rtk-savings.md](rtk-savings.md).
- **The hook cut far more per output, but costs time and money each call**, and only two runs
  were measured. It was switched off after the trial; see [../docs/02-trial-on-acme.md](../docs/02-trial-on-acme.md).
- **They can run together.** Our hook puts itself in front of rtk: it takes the large search and
  log commands, and rtk keeps everything else.

## Running the measurement

```
python rtk/tool/rtk-savings.py --workspace <your project folder name>
python rtk/tool/rtk-savings.py --html out.html
python -m unittest rtk/tool/test_rtk_savings.py
```

It reads rtk's history database (read-only): `%LOCALAPPDATA%\rtk\history.db` on Windows,
`~/Library/Application Support/rtk/history.db` on Mac, `~/.local/share/rtk/history.db` on Linux.
