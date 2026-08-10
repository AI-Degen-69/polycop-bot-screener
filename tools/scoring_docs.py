#!/usr/bin/env python3
"""Render the scoring documentation from the code's single source of truth.

The gate thresholds, parameter weights and tier bands live as constants in
`app/src/screener/score_wallets.py`, assembled into `SCORING_SPEC`. This script
renders the canonical markdown block from that spec and either writes it into
`.agents/AGENTS.md` and `README.md` (between the SCORING-SPEC markers) or checks
that the committed docs still match. It does the same for the tier floors and
gem threshold embedded in the web UI (`app/web/index.html` and
`app/web/js/app.js`), so a band recalibration cannot silently leave a stale
label on the page.

Usage:
    python tools/scoring_docs.py generate   # rewrite the generated blocks and UI labels
    python tools/scoring_docs.py check      # fail (exit 1) on any divergence

The CI drift check runs `check`. A deliberate mismatch is caught because the
rendered text is produced from the constants, never from the prose: change a
gate or tier floor in the code and the docs or UI disagree until they are
regenerated.
"""
import os
import re
import sys

# The expected labels contain non-ASCII glyphs (e.g. ≥). Force UTF-8 on stdout
# so the failure messages render on consoles whose default codec is narrower
# (e.g. cp1255/cp1252 on Windows), rather than crashing mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.score_wallets import (  # noqa: E402
    GEM_SITE_SCORE_MAX,
    MARKETS_GATE,
    MODELLED_COPY_PNL_MIN_USD,
    PL_RATIO_GATE,
    SCORING_SPEC,
)
from execution.copy_execution_profile import CURRENT_PROFILE  # noqa: E402

BEGIN_MARKER = "<!-- SCORING-SPEC:BEGIN -->"
END_MARKER = "<!-- SCORING-SPEC:END -->"

DOCS = [
    os.path.join(PROJECT_ROOT, ".agents", "AGENTS.md"),
    os.path.join(PROJECT_ROOT, "README.md"),
]

CONTEXT_MD = os.path.join(PROJECT_ROOT, "CONTEXT.md")

WEB_DIR = os.path.join(PROJECT_ROOT, "app", "web")


def _tier_min(label_prefix: str) -> float:
    """The floor of the SCORING_SPEC tier whose label starts with `label_prefix`."""
    for tier in SCORING_SPEC["tiers"]:
        if tier["label"].startswith(label_prefix):
            return tier["min"]
    raise RuntimeError(f"No SCORING_SPEC tier starts with {label_prefix!r}")


TIER_S_MIN = _tier_min("S-Tier")
TIER_A_MIN = _tier_min("A-Tier")

# The tier floors and gem threshold as they appear in the web UI, each rendered
# from the code constants. `expected` is the exact label string the shipped
# asset must contain; `pattern` locates the label (swapping any old numeric
# value) so `generate` can update it in place.
UI_LABELS = [
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "S-Tier stat pill floor",
        "expected": f"S-Tier (\u2265{TIER_S_MIN:.0f})",
        "pattern": r"S-Tier \(\u2265\d+\)",
    },
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "gem info card site-score ceiling",
        "expected": f"PolyCop Score &lt; {GEM_SITE_SCORE_MAX:.0f}",
        "pattern": r"PolyCop Score &lt; \d+",
    },
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "gem info card A-Tier floor",
        "expected": f"A-Tier Screener Score (&ge;{TIER_A_MIN:.0f})",
        "pattern": r"A-Tier Screener Score \(&ge;\d+\)",
    },
    {
        "relpath": os.path.join("app", "web", "js", "app.js"),
        "description": "gem tooltip site-score ceiling",
        "expected": f"site score (&lt;{GEM_SITE_SCORE_MAX:.0f})",
        "pattern": r"site score \(&lt;\d+\)",
    },
    {
        "relpath": os.path.join("app", "web", "js", "app.js"),
        "description": "gem tooltip A-Tier floor",
        "expected": f"A-Tier Screener Score (&ge;{TIER_A_MIN:.0f})",
        "pattern": r"A-Tier Screener Score \(&ge;\d+\)",
    },
]

# Gate values, the gate count and the bankroll as they appear in the web
# assets. The gem card's gate count and the tooltip gate values all trace to
# SCORING_SPEC constants, so a gate recalibration regenerates them the same way
# a band recalibration regenerates the tier pills.
GATE_AND_PROFILE_LABELS = [
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "Toxic Copy Poison gate tooltip value",
        "expected": f"&lt; ${MODELLED_COPY_PNL_MIN_USD:.0f} (Toxic Copy Poison)",
        "pattern": r"&lt; \$\d+ \(Toxic Copy Poison\)",
    },
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "Profit/Loss gate tooltip value",
        "expected": f"&lt; {PL_RATIO_GATE:.1f}x",
        "pattern": r"&lt; [\d.]+x",
    },
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "Markets Sample gate tooltip value",
        "expected": f"Rejects &lt; {MARKETS_GATE:.0f} (lucky streak risk)",
        "pattern": r"Rejects &lt; \d+ \(lucky streak risk\)",
    },
    {
        "relpath": os.path.join("app", "web", "js", "app.js"),
        "description": "hard rejection gate count (gem tooltip)",
        "expected": f"passes all {len(SCORING_SPEC['gates'])} Hard Rejection Gates",
        "pattern": r"passes all \d+ Hard Rejection Gates",
    },
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "copy bankroll phrase",
        "expected": f"${CURRENT_PROFILE.bankroll_usd:.0f} Bankroll",
        "pattern": r"\$\d+ Bankroll",
    },
    {
        "relpath": os.path.join("app", "web", "index.html"),
        "description": "copy bankroll phrase (prose)",
        "expected": f"${CURRENT_PROFILE.bankroll_usd:.0f} bankroll",
        "pattern": r"\$\d+ bankroll",
    },
]



UI_LABELS.extend(GATE_AND_PROFILE_LABELS)


def render_block() -> str:
    """The canonical markdown block, generated entirely from SCORING_SPEC."""
    lines = [
        BEGIN_MARKER,
        "",
        "### Scoring Engine — Gates, Parameters and Tiers",
        "",
        "> This section is generated from `app/src/screener/score_wallets.py` via",
        "> `tools/scoring_docs.py`. Do not edit it by hand — change the code and run",
        "> `python tools/scoring_docs.py generate`, or CI will fail the drift check.",
        "",
        "#### Hard Rejection Gates (instant disqualification, never traded off)",
        "",
        "| Gate | Condition | Why |",
        "| :--- | :--- | :--- |",
    ]
    for gate in SCORING_SPEC["gates"]:
        lines.append(
            f"| {gate['name']} | `{gate['condition']}` | {gate['reason']} |"
        )
    lines += [
        "",
        "#### Continuous Parameters (100 points total)",
        "",
        "| Parameter | Points | Zero points | Full marks |",
        "| :--- | :---: | :--- | :--- |",
    ]
    for param in SCORING_SPEC["parameters"]:
        note = f" — {param['note']}" if param["note"] else ""
        lines.append(
            f"| {param['name']} | {param['points']} | {param['zero']} | "
            f"{param['full']}{note} |"
        )
    lines += [
        "",
        "#### Copyability Score Tier Bands (triage only — verdicts come from simulation)",
        "",
        "| Tier | Score |",
        "| :--- | :--- |",
    ]
    for tier in SCORING_SPEC["tiers"]:
        if tier["min"] is None:
            score = f"< {SCORING_SPEC['tiers'][-2]['min']:.0f}"
        else:
            score = f"&ge; {tier['min']:.0f}"
        lines.append(f"| {tier['label']} | {score} |")
    lines += [
        "",
        "#### Simulated Verdict Tier Bands (Edge Retention — the verdict)",
        "",
        "| Tier | Edge Retention |",
        "| :--- | :--- |",
    ]
    for tier in SCORING_SPEC["sim_tiers"]:
        if tier["min"] is None:
            score = f"< {SCORING_SPEC['sim_tiers'][-2]['min']:.2f}"
        else:
            score = f"&ge; {tier['min']:.2f}"
        lines.append(f"| {tier['label']} | {score} |")
    lines += ["", END_MARKER, ""]
    return "\n".join(lines)


def _extract_block(path: str):
    """Return (block_text, rest_without_block) for a doc, or (None, text)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    match = re.search(
        re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER), text, re.S
    )
    if not match:
        return None, text
    return match.group(0), text


def generate_ui(ui_overrides=None) -> None:
    """Swap the rendered tier/gem labels into the shipped web assets.

    `ui_overrides` maps a UI_LABELS `relpath` to a replacement absolute path,
    so tests can point `generate` at temp copies instead of the repo.
    """
    for label in UI_LABELS:
        path = ui_overrides.get(label["relpath"]) if ui_overrides else None
        path = path or os.path.join(PROJECT_ROOT, label["relpath"])
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        new_text, count = re.subn(label["pattern"], label["expected"], text)
        if count == 0:
            print(
                f"[generate] {label['relpath']}: {label['description']} label not "
                f"found — skipped (expected {label['expected']!r})"
            )
            continue
        if new_text != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
            print(f"[generate] updated {label['relpath']} ({label['description']})")


def generate(doc_paths=None, ui_overrides=None) -> None:
    """Rewrite the generated blocks and UI labels from the code constants.

    `doc_paths` and `ui_overrides` are overridable so tests can point the
    generator at temp copies without touching the repo.
    """
    block = render_block()
    for path in (doc_paths or DOCS):
        existing, text = _extract_block(path)
        if existing is None:
            # No markers yet: append the block. The canonical form ends the
            # marker on `\n\n`, so a fresh doc is byte-stable on the very
            # first run — the next generate must not produce a diff.
            new_text = text.rstrip() + "\n\n" + block.rstrip("\n") + "\n\n"
        else:
            # Swap the canonical block in, also consuming any blank lines that
            # trail the END marker, so the result is byte-stable: re-running
            # generate on a synced tree must not produce a diff.
            pattern = re.compile(
                re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER)
                + r"[ \t]*\n*",
                re.S,
            )
            new_text = pattern.sub(block.rstrip("\n") + "\n\n", text)
        if new_text != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
            print(f"[generate] updated {os.path.relpath(path, PROJECT_ROOT)}")
    generate_ui(ui_overrides)


def check_ui(ui_overrides=None) -> list:
    """Problems from the web UI labels, or [] when every label matches.

    `ui_overrides` maps a UI_LABELS `relpath` to a replacement absolute path, so
    the check can be pointed at tampered copies in tests.
    """
    problems = []
    for label in UI_LABELS:
        path = ui_overrides.get(label["relpath"]) if ui_overrides else None
        path = path or os.path.join(PROJECT_ROOT, label["relpath"])
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # The expected string must be present, and every match of the pattern
        # must carry that exact value — a stale duplicate in the same format
        # (e.g. a hand-edited `S-Tier (≥99)` next to a correct `S-Tier (≥72)`)
        # must not slip through a substring check.
        matches = re.findall(label["pattern"], text)
        if label["expected"] not in text or any(m != label["expected"] for m in matches):
            problems.append(
                f"{label['relpath']} {label['description']} is stale — expected "
                f"{label['expected']!r} (run `python tools/scoring_docs.py generate`)"
            )
    return problems


def check(doc_paths=None, ui_overrides=None) -> int:
    """Return 0 when the docs and UI match the code, 1 otherwise.

    `doc_paths` and `ui_overrides` are overridable so the check can be pointed
    at tampered copies in tests — the acceptance criterion for the drift check
    is that a deliberate mismatch fails it, and that must be assertable, not
    just demonstrable.
    """
    block = render_block()
    problems = []
    for path in (doc_paths or DOCS):
        existing, _ = _extract_block(path)
        if existing is None:
            problems.append(
                f"{os.path.relpath(path, PROJECT_ROOT)} has no SCORING-SPEC block "
                f"(run `python tools/scoring_docs.py generate`)"
            )
        elif existing.strip() != block.strip():
            problems.append(
                f"{os.path.relpath(path, PROJECT_ROOT)} disagrees with the code — "
                f"run `python tools/scoring_docs.py generate`"
            )
    problems.extend(check_ui(ui_overrides))
    # CONTEXT.md is a domain glossary: no numeric thresholds may appear in it.
    with open(CONTEXT_MD, "r", encoding="utf-8") as f:
        context_text = f.read()
    if re.search(r"\d", context_text):
        problems.append("CONTEXT.md contains numeric values; it must stay threshold-free")

    for problem in problems:
        print(f"[check] FAIL: {problem}")
    if problems:
        print("[check] Run `python tools/scoring_docs.py generate` and commit the result.")
        return 1
    print("[check] OK: docs and UI labels match the code")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        generate()
    else:
        sys.exit(check())
