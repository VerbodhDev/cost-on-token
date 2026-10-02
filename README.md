# Cost on Token

How much of Claude Code's token bill is tool output, and two ways to cut it: **rtk**, which
shortens command output, and a **context-diet hook**, which has Sonnet 5.5 replace large
search and log outputs with a short fact list.

## Findings

| | Result |
|---|---|
| rtk in the AcmeProducts folder | 24.8% cut, and 80% of runs not measured at all |
| rtk's own headline (`rtk gain`) | 95.6%, inflated by six bogus grep rows |
| Context-diet hook, trial | 2 real greps, ~7,285 → ~999 tokens (86.3% cut), ~10 s and one Sonnet call each |
| Status | hook uninstalled; plain rtk is in use |

Full side-by-side comparison: [rtk/README.md](rtk/README.md#rtk-compared-with-the-context-diet-hook).

## Read in this order

1. [docs/01-source-claude-context-diet.md](docs/01-source-claude-context-diet.md): the public
   page the hook idea came from, copied as text
2. [rtk/README.md](rtk/README.md): what rtk is, and how it compares with the hook
3. [rtk/rtk-savings.md](rtk/rtk-savings.md): what rtk really saves, by command type
4. [docs/02-trial-on-acme.md](docs/02-trial-on-acme.md): our version of the hook, what was
   tested, what was not proved, and why it was switched off

## Folders

| Folder | What is in it |
|---|---|
| `prompt/` | [implement-context-diet.md](prompt/implement-context-diet.md): a prompt to paste into Claude Code so it installs the hook in your own project, step by step |
| `rtk/` | rtk ([github.com/rtk-ai/rtk](https://github.com/rtk-ai/rtk)): what it is, the comparison, our measurement, and `tool/rtk-savings.py` with its tests |
| `docs/` | the context-diet hook: the source page and our trial |
| `reference/original-hook/` | the hook script and settings block exactly as the source page gave them; written outside Acme, not reviewed, never installed |
| `implementation/hooks/` | our hook: `compress-tool-output.py`, the per-laptop installer and the tests |

## Running it

The code in `implementation/` and `rtk/tool/` is a copy. The copies in use live in the AcmeProducts workspace:
`.agents/hooks/shared/` (hook) and `mcp/tools/` (rtk report). Run them from there, because both
find the workspace folder from where the script sits.

```
python mcp/tools/rtk-savings.py --html                          # rtk report
python  .agents/hooks/shared/install-compress-hook.py           # turn the hook on (Windows)
python3 .agents/hooks/shared/install-compress-hook.py           # turn the hook on (Mac)
python  .agents/hooks/shared/install-compress-hook.py --uninstall
```

Tests, from this repo:

```
python implementation/hooks/test_compress_tool_output.py
python -m unittest rtk/tool/test_rtk_savings.py
```
