# What rtk actually saves

- **Tool:** [implementation/tools/rtk-savings.py](../implementation/tools/rtk-savings.py), reads rtk's own history database
- **Data:** one Windows laptop, rtk 0.38, about three months of runs

## Result

| Scope | Raw tokens | Sent to Claude | Cut | Runs rtk did not measure |
|---|---|---|---|---|
| AcmeProducts folder | 3,881,718 | 2,917,396 | -24.8% | 16,730 of 20,832 (80%) |
| Whole laptop | 30,557,415 | 6,739,699 | -77.9% | 19,067 of 36,258 (53%) |
| What `rtk gain` claims | 153,788,681 | 6,767,757 | -95.6% | ← wrong |

## Why `rtk gain` is wrong

- Six one-file greps (for example `grep -rn … package.json`) were logged at about 123 million raw
  tokens between them. A grep on one file cannot print that much, so the tool leaves any grep
  over 1 million raw tokens out of the totals and lists it instead.
- Commands rtk has no filter for run as normal and are logged at zero tokens. In the
  AcmeProducts folder that was 80% of all runs, so their output is in no total.

## Where rtk helps least in the AcmeProducts folder

| Source | Raw | Sent | Cut |
|---|---|---|---|
| git | 2,120,176 | 2,095,364 | -1.2% ← worst; one `git show` of a SQLite file was 1.88M tokens |
| File reads | 657,118 | 331,088 | -49.6% |
| rtk proxy (full output on purpose) | 358,860 | 358,860 | 0.0% |
| grep / rg | 340,581 | 49,902 | -85.3% |
| curl | 150,954 | 6,093 | -96.0% |
| ls / find / wc / diff | 143,866 | 48,735 | -66.1% |
| Test and build logs | 92,393 | 24,529 | -73.5% |
| Cloud and infra | 17,770 | 2,825 | -84.1% |

This is what led to trying the context-diet hook: [03-trial-on-acme.md](03-trial-on-acme.md).
