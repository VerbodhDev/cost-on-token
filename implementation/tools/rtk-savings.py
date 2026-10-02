"""Report how many tokens rtk cut from command output, by kind of command.

Reads rtk's own history database (read-only) and answers: of everything the commands
printed, how much did Claude actually receive? Prints a table, and can write the same
report as a standalone HTML page with a "this workspace / whole laptop" switch.

    python mcp/tools/rtk-savings.py                         # table in the terminal
    python mcp/tools/rtk-savings.py --html                  # also write mcp/tools/reports/rtk-savings.html
    python mcp/tools/rtk-savings.py --html out.html --json out.json
    python mcp/tools/rtk-savings.py --since 2026-09-01      # only runs from that date on
    python mcp/tools/rtk-savings.py --db path/to/history.db # a copy from the other laptop

WHY IT DOES NOT TRUST `rtk gain`
--------------------------------
1. **Bogus grep rows are left out.** rtk has logged one-file greps (`grep -rn x package.json`)
   at 20-40 million raw tokens. A grep that prints that much in one run is a logging error,
   so any grep run above OUTLIER_TOKENS raw is excluded from the totals and listed instead.
2. **Fallback runs are counted, not measured.** A command rtk has no filter for runs as
   normal and is logged with zero tokens. The report says how many runs that was, because
   their output is in the conversation but in no total.
3. **Token counts are rtk's estimates**, not the model's tokenizer.

The database lives in rtk's data folder: %LOCALAPPDATA%\\rtk\\history.db on Windows,
~/Library/Application Support/rtk/history.db on the Mac, ~/.local/share/rtk/history.db on Linux.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_HTML = Path(__file__).resolve().parent / "reports" / "rtk-savings.html"
OUTLIER_TOKENS = 1_000_000
FALLBACK = "fallback"

# Report row -> rtk_cmd prefixes. Order is the order rows are checked in.
CATEGORIES = [
    ("grep / rg", ["rtk grep", "rtk rg"]),
    ("File reads", ["rtk read"]),
    ("git", ["rtk git"]),
    ("ls / find / wc / diff", ["rtk ls", "rtk find", "rtk wc", "rtk diff", "rtk tree"]),
    ("curl (APIs, local servers)", ["rtk curl", "rtk wget"]),
    ("Test and build logs", ["rtk cargo", "rtk npm", "rtk npx", "rtk pnpm", "rtk tsc", "rtk next", "rtk lint",
                             "rtk pip", "rtk uv", "rtk pytest", "rtk vitest", "rtk:toml uv"]),
    ("Cloud and infra", ["rtk aws", "rtk docker", "rtk kubectl", "rtk gh", "rtk:toml"]),
    ("Passed through unfiltered (rtk proxy)", ["rtk proxy"]),
]


def default_db() -> Path:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "rtk" / "history.db",
        Path.home() / "Library" / "Application Support" / "rtk" / "history.db",
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "rtk" / "history.db",
    ]
    return next((p for p in candidates if p.is_file()), candidates[0])


def category(rtk_cmd: str) -> str:
    if rtk_cmd.startswith("rtk fallback"):
        return FALLBACK
    for name, prefixes in CATEGORIES:
        if any(rtk_cmd == p or rtk_cmd.startswith(p + " ") or (p.endswith(":toml") and rtk_cmd.startswith(p))
               for p in prefixes):
            return name
    return "Other"


def load_rows(db: Path, since: str | None = None) -> list[tuple]:
    """(rtk_cmd, original_cmd, input, output, project_path, timestamp) for every logged run."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        sql = ("SELECT rtk_cmd, original_cmd, input_tokens, output_tokens, project_path, timestamp"
               " FROM commands")
        args: tuple = ()
        if since:
            sql, args = sql + " WHERE timestamp >= ?", (since,)
        return con.execute(sql + " ORDER BY timestamp", args).fetchall()
    finally:
        con.close()


def is_outlier(row: tuple) -> bool:
    return category(row[0]) == "grep / rg" and row[2] > OUTLIER_TOKENS


def summarise(rows: list[tuple]) -> dict:
    cats: OrderedDict[str, list[int]] = OrderedDict()
    big: dict[str, list] = {}
    fallback = 0
    for cmd, orig, i, o, _path, _ts in rows:
        k = category(cmd)
        if k == FALLBACK:
            fallback += 1
            continue
        c = cats.setdefault(k, [0, 0, 0])
        c[0] += 1
        c[1] += i
        c[2] += o
        if i > big.get(k, [0])[0]:
            big[k] = [i, orig[:100]]
    ordered = OrderedDict(sorted(cats.items(), key=lambda kv: -kv[1][1]))
    return {"cats": ordered, "fallback": fallback, "runs": len(rows), "big": big}


def build_report(rows: list[tuple], workspace: str = WORKSPACE.name) -> dict:
    clean = [r for r in rows if not is_outlier(r)]
    in_ws = [r for r in clean if workspace.lower() in (r[4] or "").lower()]
    return {
        "workspace": workspace,
        "range": [rows[0][5][:10], rows[-1][5][:10]] if rows else ["", ""],
        "rtk_headline": {"input": sum(r[2] for r in rows), "output": sum(r[3] for r in rows)},
        "outliers": [[r[2], r[3], r[1][:100], r[5][:10]] for r in rows if is_outlier(r)],
        "scopes": {"ws": summarise(in_ws), "all": summarise(clean)},
    }


def pct_cut(i: int, o: int) -> str:
    return f"-{100 * (1 - o / i):.1f}%" if i and o < i else "0.0%"


def print_report(rep: dict) -> None:
    head = rep["rtk_headline"]
    print(f"rtk history {rep['range'][0]} to {rep['range'][1]}")
    print(f"rtk gain would say: {head['input']:,} raw -> {head['output']:,} sent "
          f"({pct_cut(head['input'], head['output'])})")
    if rep["outliers"]:
        print(f"Left out: {len(rep['outliers'])} bogus grep runs, "
              f"{sum(o[0] for o in rep['outliers']):,} raw tokens between them")
    for key, label in (("ws", f"{rep['workspace']} folder"), ("all", "Whole laptop")):
        s = rep["scopes"][key]
        print(f"\n{label}")
        print(f"  {'Source':40} {'Runs':>7} {'Raw':>13} {'Sent':>12} {'Cut':>8}")
        ti = to = 0
        for name, (n, i, o) in s["cats"].items():
            ti, to = ti + i, to + o
            print(f"  {name:40} {n:>7,} {i:>13,} {o:>12,} {pct_cut(i, o):>8}")
        print(f"  {'Total':40} {s['runs'] - s['fallback']:>7,} {ti:>13,} {to:>12,} {pct_cut(ti, to):>8}")
        if s["runs"]:
            print(f"  Not measured (no rtk filter): {s['fallback']:,} of {s['runs']:,} runs "
                  f"({round(100 * s['fallback'] / s['runs'])}%)")


def write_html(rep: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HTML.replace("__DATA__", json.dumps(rep)), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=None, help="rtk history.db (default: rtk's data folder)")
    ap.add_argument("--since", help="only runs on or after this date, YYYY-MM-DD")
    ap.add_argument("--workspace", default=WORKSPACE.name, help="folder name for the workspace scope")
    ap.add_argument("--html", nargs="?", const=DEFAULT_HTML, type=Path, help="write the HTML report")
    ap.add_argument("--json", type=Path, help="write the report data as JSON")
    a = ap.parse_args(argv)

    db = a.db or default_db()
    if not db.is_file():
        print(f"rtk history not found at {db}. Pass --db.", file=sys.stderr)
        return 1
    rows = load_rows(db, a.since)
    if not rows:
        print("No rtk runs in that range.", file=sys.stderr)
        return 1
    rep = build_report(rows, a.workspace)
    print_report(rep)
    if a.html:
        write_html(rep, a.html)
        print(f"\nHTML report: {a.html}")
    if a.json:
        a.json.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        print(f"JSON data: {a.json}")
    return 0


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RTK Token Savings</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
/* Layout: one reading column; a single ledger table is the page, notes sit under it */
:root{
  --bg:#f3f5f6; --card:#ffffff; --fg:#14181b; --muted:#5d6870; --line:#dfe4e7;
  --raw:#c3ccd3; --sent:#106b7c; --total:#d8ebf2; --warn:#a14a12; --warnbg:#fbf0e6;
  --display:"Archivo",system-ui,sans-serif; --body:"IBM Plex Sans",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#101416; --card:#171d20; --fg:#e7ecee; --muted:#93a1a9; --line:#2a3337;
  --raw:#4a565d; --sent:#3fb4c7; --total:#16323a; --warn:#f0a36b; --warnbg:#2b1f15; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#101416; --card:#171d20; --fg:#e7ecee; --muted:#93a1a9; --line:#2a3337;
  --raw:#4a565d; --sent:#3fb4c7; --total:#16323a; --warn:#f0a36b; --warnbg:#2b1f15; color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:16px/1.6 var(--body);margin:0;padding:32px 16px 56px}
main{max-width:1000px;margin:0 auto;display:grid;gap:22px}
h1{font:800 clamp(28px,4.5vw,40px)/1.1 var(--display);margin:0;letter-spacing:-.01em;text-wrap:balance}
.lede{max-width:65ch;margin:0}
.bar{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--muted);font-size:14px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:var(--card)}
.seg button{font:500 14px var(--body);color:var(--muted);background:none;border:0;padding:7px 14px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--sent);color:var(--card)}
.seg button:focus-visible{outline:2px solid var(--sent);outline-offset:-2px}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;min-width:0}
table{width:100%;border-collapse:collapse;min-width:680px}
th{font:500 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:right;padding:14px 18px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
td{padding:14px 18px;border-bottom:1px solid var(--line);text-align:right;font:400 15px var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
td:first-child{font:400 15px var(--body);white-space:normal;min-width:220px}
td small{display:block;color:var(--muted);font-size:12.5px;line-height:1.4;margin-top:2px}
th:last-child,td:last-child{text-align:left;width:200px}
.sc{display:grid;gap:4px}
.sc span{display:block;height:8px;border-radius:2px;min-width:2px}
.sc .r{background:var(--raw)} .sc .s{background:var(--sent)}
tr.total td{background:var(--total);font-weight:700;border-bottom:0}
tr.zero td{color:var(--muted)}
tr.zero td:first-child{color:var(--fg)}
.notes{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.note{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;min-width:0}
.note h2{font:700 15px var(--display);margin:0 0 6px}
.note p{margin:0;font-size:14.5px;color:var(--muted)}
.note b{color:var(--fg);font-variant-numeric:tabular-nums}
.note.warn{background:var(--warnbg);border-color:transparent}
.note.warn h2{color:var(--warn)}
.foot{font-size:13px;color:var(--muted);margin:0}
code{font:13px var(--mono);overflow-wrap:anywhere}
</style></head><body>
<main>
  <h1>Where rtk saves tokens</h1>
  <p class="lede">rtk shortens command output before Claude reads it. <b>Raw</b> is what the command printed. <b>Sent</b> is what reached Claude after rtk cut it down. Every tool result stays in the conversation, so each token cut is saved again on every later turn.</p>
  <div class="bar">
    <div class="legend"><span><i style="background:var(--raw)"></i>Raw output</span><span><i style="background:var(--sent)"></i>What Claude got</span></div>
    <div class="seg" role="group" aria-label="Scope">
      <button id="b-ws" type="button" aria-pressed="true"></button>
      <button id="b-all" type="button" aria-pressed="false">Whole laptop</button>
    </div>
  </div>
  <div class="wrap"><table>
    <thead><tr><th>Source</th><th>Runs</th><th>Raw</th><th>Sent</th><th>Cut</th><th>Scale</th></tr></thead>
    <tbody id="rows"></tbody>
  </table></div>
  <div class="notes" id="notes"></div>
  <p class="foot" id="foot"></p>
</main>
<script>
const D=__DATA__;
const fmt=n=>n.toLocaleString('en-US');
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.getElementById('b-ws').textContent=D.workspace;
function noteFor(k,s,raw){
  if(k.startsWith('Passed')) return 'These runs asked for full output on purpose, so nothing was cut.';
  const b=s.big[k];
  if(b&&raw&&b[0]>=raw/2) return `One run, <code>${esc(b[1])}</code>, printed ${fmt(b[0])} raw tokens: ${Math.round(100*b[0]/raw)}% of this row.`;
  return '';
}
function render(scope){
  const s=D.scopes[scope], rows=Object.entries(s.cats);
  const max=Math.max(1,...rows.map(r=>r[1][1]));
  let tr=0,ti=0,to=0,h='';
  for(const [k,[n,i,o]] of rows){
    tr+=n;ti+=i;to+=o;
    const cut=i?-(100*(1-o/i)):0, note=noteFor(k,s,i);
    h+=`<tr class="${cut>-5?'zero':''}"><td>${esc(k)}${note?`<small>${note}</small>`:''}</td><td>${fmt(n)}</td><td>${fmt(i)}</td><td>${fmt(o)}</td><td>${cut.toFixed(1)}%</td>`+
       `<td><div class="sc"><span class="r" style="width:${100*i/max}%"></span><span class="s" style="width:${100*o/max}%"></span></div></td></tr>`;
  }
  h+=`<tr class="total"><td>Total</td><td>${fmt(tr)}</td><td>${fmt(ti)}</td><td>${fmt(to)}</td><td>${ti?(-(100*(1-to/ti))).toFixed(1):'0.0'}%</td><td></td></tr>`;
  document.getElementById('rows').innerHTML=h;
  const H=D.rtk_headline, outIn=D.outliers.reduce((a,o)=>a+o[0],0);
  let notes='';
  if(D.outliers.length) notes+=`<div class="note warn"><h2>rtk's own headline is inflated</h2><p><code>rtk gain</code> reports <b>${(100*(1-H.output/H.input)).toFixed(1)}%</b> cut on <b>${fmt(H.input)}</b> raw tokens. But <b>${D.outliers.length}</b> grep runs, such as <code>${esc(D.outliers[0][2])}</code>, were logged at <b>${fmt(outIn)}</b> raw tokens between them. A grep cannot print that much in one run, so this table leaves them out.</p></div>`;
  if(s.runs) notes+=`<div class="note"><h2>Runs rtk did not measure</h2><p><b>${fmt(s.fallback)}</b> of <b>${fmt(s.runs)}</b> runs (${Math.round(100*s.fallback/s.runs)}%) had no rtk filter and ran as normal. rtk logs them at zero tokens, so their output is missing from the table.</p></div>`;
  document.getElementById('notes').innerHTML=notes;
  document.getElementById('foot').textContent=`Source: rtk history, ${D.range[0]} to ${D.range[1]}. Token counts are rtk's own estimates. `+
    (scope==='ws'?`Scope: commands run inside the ${D.workspace} folder.`:'Scope: every folder on this laptop.');
}
for(const id of ['ws','all']){
  document.getElementById('b-'+id).addEventListener('click',()=>{
    for(const j of ['ws','all']) document.getElementById('b-'+j).setAttribute('aria-pressed',String(j===id));
    try{localStorage.setItem('scope',id)}catch(e){}
    render(id);
  });
}
let start='ws';try{start=localStorage.getItem('scope')||'ws'}catch(e){}
document.getElementById('b-'+(D.scopes[start]?start:'ws')).click();
</script></body></html>
"""

if __name__ == "__main__":
    sys.exit(main())
