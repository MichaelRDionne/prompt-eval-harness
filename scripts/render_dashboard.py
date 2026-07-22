#!/usr/bin/env python3
"""Render the static eval dashboard (docs/index.html) from benchmarks/results.jsonl.

Dependency-free, like the rest of the repo. The page is fully self-contained
(inline CSS/SVG, a few lines of vanilla JS for tooltips) and is served by
GitHub Pages from the docs/ folder. The weekly eval workflow re-runs this
after each eval run and commits the result, so the published page always
shows the latest scores.

Usage:
    python scripts/render_dashboard.py

Date handling follows the repo rule: the page's "last run" stamp comes from
the newest results row, never from a live clock read, so output is
reproducible for a given data file.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "benchmarks" / "results.jsonl"
CASES_PATH = REPO_ROOT / "examples" / "generic_eval.jsonl"
OUT_PATH = REPO_ROOT / "docs" / "index.html"

REPO_URL = "https://github.com/MichaelRDionne/prompt-eval-harness"
MODEL_ID = "claude-haiku-4-5-20251001"
GATE_THRESHOLD = 0.9

# One-line "what this case catches" blurbs, keyed by case id. Falls back to
# the raw check names for any case added without a blurb.
CASE_BLURBS = {
    "changelog-preserves-breaking-change": "A fluent summary that quietly drops the breaking-change notice.",
    "changelog-preserves-deprecation": "A rewrite that loses the deprecation warning.",
    "json-extraction-no-hallucinated-field": "Structured extraction that invents a field nobody asked for.",
    "status-update-word-limit": "An update that fits the word budget but drops the exact error code.",
    "prompt-injection-resistance": "A summary task that folds under instructions embedded in the input.",
    "preserves-precise-metric": "A recap that rounds away the one figure the task said to keep exact.",
}

# Chart geometry.
CHART_W, CHART_H = 720, 240
PAD_L, PAD_R, PAD_T, PAD_B = 48, 16, 28, 36


def load_history() -> list[dict]:
    return [
        json.loads(line)
        for line in RESULTS_PATH.read_text().splitlines()
        if line.strip()
    ]


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in CASES_PATH.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def render_chart(history: list[dict]) -> str:
    """Inline SVG: score per run, dots colored by mode, a line through the
    live runs (the trend that matters). Hover targets carry data-* attrs the
    page JS turns into a tooltip.
    """
    n = len(history)
    plot_w = CHART_W - PAD_L - PAD_R
    plot_h = CHART_H - PAD_T - PAD_B

    def x_at(i: int) -> float:
        if n == 1:
            return PAD_L + plot_w / 2
        return PAD_L + i * plot_w / (n - 1)

    def y_at(score: float) -> float:
        return PAD_T + plot_h * (1 - score)

    grid = []
    for frac, label in ((0.0, "0%"), (0.25, "25%"), (0.5, "50%"), (0.75, "75%"), (1.0, "100%")):
        y = y_at(frac)
        grid.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{CHART_W - PAD_R}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{PAD_L - 8}" y="{y + 4:.1f}" class="axis" text-anchor="end">{label}</text>'
        )

    # X tick labels, thinned so they never collide.
    every = max(1, (n + 7) // 8)
    ticks = []
    for i, row in enumerate(history):
        if i % every == 0 or i == n - 1:
            anchor = "end" if i == n - 1 and n > 1 else "middle"
            ticks.append(
                f'<text x="{x_at(i):.1f}" y="{CHART_H - 12}" class="axis" text-anchor="{anchor}">{html.escape(row["date"])}</text>'
            )

    live_pts = [(i, r) for i, r in enumerate(history) if r["mode"] == "live"]
    line = ""
    if len(live_pts) > 1:
        pts = " ".join(f"{x_at(i):.1f},{y_at(r['score']):.1f}" for i, r in live_pts)
        line = f'<polyline points="{pts}" class="line-live"/>'

    dots, targets = [], []
    for i, row in enumerate(history):
        x, y = x_at(i), y_at(row["score"])
        cls = "dot-live" if row["mode"] == "live" else "dot-mock"
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="{cls}"/>')
        n_passed = round(row["pass_rate"] * row["n"])
        targets.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" class="hit" '
            f'data-date="{html.escape(row["date"])}" data-mode="{html.escape(row["mode"])}" '
            f'data-score="{row["score"]:.1%}" data-cases="{n_passed}/{row["n"]}" '
            f'data-gate="{"PASS" if row.get("gate_pass") else "FAIL"}"/>'
        )

    # Direct label on the newest run only (selective labeling).
    last_i, last = n - 1, history[-1]
    label = (
        f'<text x="{x_at(last_i):.1f}" y="{y_at(last["score"]) - 10:.1f}" '
        f'class="pt-label" text-anchor="middle">{last["score"]:.0%}</text>'
    )

    modes = {r["mode"] for r in history}
    legend = ""
    if len(modes) > 1:
        legend = (
            f'<g transform="translate({PAD_L}, 2)" font-size="11">'
            '<circle cx="4" cy="6" r="4" class="dot-live"/>'
            '<text x="13" y="10" class="axis">live (Haiku)</text>'
            '<circle cx="104" cy="6" r="4" class="dot-mock"/>'
            '<text x="113" y="10" class="axis">deterministic mock</text>'
            "</g>"
        )

    return (
        f'<svg viewBox="0 0 {CHART_W} {CHART_H}" role="img" '
        f'aria-label="Weighted score per eval run">'
        f'{"".join(grid)}{"".join(ticks)}{legend}{line}{"".join(dots)}{label}{"".join(targets)}'
        "</svg>"
    )


def render_page(history: list[dict], cases: list[dict]) -> str:
    latest = history[-1]
    live_runs = [r for r in history if r["mode"] == "live"]
    headline = live_runs[-1] if live_runs else latest
    headline_mode = "live" if live_runs else latest["mode"]
    n_passed = round(headline["pass_rate"] * headline["n"])
    gate_pass = headline.get("gate_pass", headline["score"] >= GATE_THRESHOLD)
    gate_word = "PASS" if gate_pass else "FAIL"
    gate_cls = "gate-pass" if gate_pass else "gate-fail"
    gate_icon = "✓" if gate_pass else "✗"
    headline_target = f"{MODEL_ID}" if headline_mode == "live" else "deterministic mock"

    mock_runs = [r for r in history if r["mode"] == "deterministic"]
    mock_note = ""
    if mock_runs:
        mock_note = (
            '<p class="sub" style="margin-top:8px; font-size:0.85rem;">The deterministic '
            "mock is a built-in fluent-but-wrong model: its output reads well and scores "
            f'{mock_runs[-1]["score"]:.0%}, which is the point — the rubric catches what '
            "eyeballing doesn't.</p>"
        )

    case_rows = []
    for c in cases:
        blurb = CASE_BLURBS.get(c["id"], "Checks: " + ", ".join(c["checks"]))
        case_rows.append(
            f"<tr><td><code>{html.escape(c['id'])}</code></td>"
            f"<td>{html.escape(blurb)}</td>"
            f"<td class='num'>{c['weight']}</td></tr>"
        )

    history_rows = []
    for row in reversed(history):
        hp = round(row["pass_rate"] * row["n"])
        hg = "PASS" if row.get("gate_pass") else "FAIL"
        history_rows.append(
            f"<tr><td>{html.escape(row['date'])}</td><td>{html.escape(row['mode'])}</td>"
            f"<td class='num'>{row['score']:.1%}</td><td class='num'>{hp}/{row['n']}</td>"
            f"<td class='{'ok' if hg == 'PASS' else 'bad'}'>{hg}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>prompt-eval-harness · live eval dashboard</title>
<style>
:root {{
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
  --live: #2a78d6; --mock: #eb6834;
  --good: #0ca30c; --bad: #d03b3b;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --live: #3987e5; --mock: #d95926;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
}}
main {{ max-width: 780px; margin: 0 auto; padding: 32px 20px 56px; }}
h1 {{ font-size: 1.35rem; margin: 0 0 2px; }}
.byline {{ color: var(--ink-2); font-size: 0.88rem; margin: 0 0 14px; }}
h2 {{ font-size: 1.02rem; margin: 34px 0 10px; }}
.sub {{ color: var(--ink-2); margin: 0 0 24px; }}
a {{ color: var(--live); }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.tile {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px;
}}
.tile .v {{ font-size: 1.7rem; font-weight: 700; }}
.tile .k {{ color: var(--muted); font-size: 0.78rem; }}
.gate-pass .v {{ color: var(--good); }}
.gate-fail .v {{ color: var(--bad); }}
.card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px; overflow-x: auto; position: relative;
}}
svg {{ width: 100%; height: auto; display: block; }}
.grid {{ stroke: var(--grid); stroke-width: 1; }}
.axis {{ fill: var(--muted); font-size: 11px; }}
.line-live {{ fill: none; stroke: var(--live); stroke-width: 2; }}
.dot-live {{ fill: var(--live); }}
.dot-mock {{ fill: var(--mock); }}
.pt-label {{ fill: var(--ink); font-size: 12px; font-weight: 600; }}
.hit {{ fill: transparent; cursor: pointer; }}
#tip {{
  position: fixed; display: none; pointer-events: none; z-index: 2;
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 10px; font-size: 12.5px; line-height: 1.45;
  box-shadow: 0 4px 14px rgba(0,0,0,0.18);
}}
table {{ border-collapse: collapse; width: 100%; font-size: 0.88rem; }}
th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--grid); }}
th {{ color: var(--muted); font-weight: 600; font-size: 0.78rem; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.ok {{ color: var(--good); font-weight: 600; }}
td.bad {{ color: var(--bad); font-weight: 600; }}
code {{ font-size: 0.85em; }}
footer {{ color: var(--muted); font-size: 0.8rem; margin-top: 40px; }}
</style>
</head>
<body>
<main>
  <h1>prompt-eval-harness</h1>
  <p class="byline">by <a href="https://github.com/MichaelRDionne">Michael R. Dionne</a> ·
  <a href="https://michaelrdionne.com">michaelrdionne.com</a></p>
  <p class="sub">Live eval dashboard — a weekly CI job scores <code>{MODEL_ID}</code>
  against a deterministic rubric suite and publishes the result here, untouched.
  All case content is synthetic. <a href="{REPO_URL}">Source &amp; docs&nbsp;→</a></p>

  <div class="tiles">
    <div class="tile"><div class="v">{headline["score"]:.0%}</div><div class="k">weighted score · latest {headline_mode} run</div></div>
    <div class="tile"><div class="v">{n_passed}/{headline["n"]}</div><div class="k">cases passed</div></div>
    <div class="tile {gate_cls}"><div class="v">{gate_icon} {gate_word}</div><div class="k">gate at {GATE_THRESHOLD:.0%} · {html.escape(headline_target)}</div></div>
    <div class="tile"><div class="v">{len(history)}</div><div class="k">runs logged · last {html.escape(latest["date"])}</div></div>
  </div>

  <h2>Score history</h2>
  <div class="card">{render_chart(history)}</div>
  {mock_note}

  <h2>What the suite checks</h2>
  <div class="card"><table>
    <thead><tr><th>case</th><th>the trap it catches</th><th class="num">weight</th></tr></thead>
    <tbody>{"".join(case_rows)}</tbody>
  </table></div>

  <h2>Run log</h2>
  <div class="card"><table>
    <thead><tr><th>date</th><th>mode</th><th class="num">score</th><th class="num">cases</th><th>gate</th></tr></thead>
    <tbody>{"".join(history_rows)}</tbody>
  </table></div>

  <footer>Built by <a href="https://github.com/MichaelRDionne">Michael R. Dionne</a>.
  Generated by <a href="{REPO_URL}/blob/master/scripts/render_dashboard.py">render_dashboard.py</a>
  from <a href="{REPO_URL}/blob/master/benchmarks/results.jsonl">benchmarks/results.jsonl</a>
  after each eval run. No numbers on this page are hand-edited.</footer>
</main>
<div id="tip"></div>
<script>
const tip = document.getElementById("tip");
document.querySelectorAll(".hit").forEach(el => {{
  el.addEventListener("mouseenter", e => {{
    const d = el.dataset;
    tip.innerHTML = `<strong>${{d.date}}</strong> · ${{d.mode}}<br>score ${{d.score}} · cases ${{d.cases}} · gate ${{d.gate}}`;
    tip.style.display = "block";
  }});
  el.addEventListener("mousemove", e => {{
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8) + "px";
    tip.style.top = (e.clientY + 14) + "px";
  }});
  el.addEventListener("mouseleave", () => tip.style.display = "none");
}});
</script>
</body>
</html>
"""


def main() -> int:
    history = load_history()
    if not history:
        print("[render_dashboard] no results in benchmarks/results.jsonl; nothing to render")
        return 1
    cases = load_cases()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_page(history, cases))
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)} ({len(history)} runs, {len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
