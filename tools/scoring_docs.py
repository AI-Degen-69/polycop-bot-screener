#!/usr/bin/env python3
"""Render the scoring documentation from the code's single source of truth.

The gate thresholds, parameter weights and tier bands live as constants in
`app/src/screener/score_wallets.py`, assembled into `SCORING_SPEC`. This script
renders the canonical markdown block from that spec and either writes it into
`.agents/AGENTS.md` and `README.md` (between the SCORING-SPEC markers) or checks
that the committed docs still match.

Usage:
    python tools/scoring_docs.py generate   # rewrite the generated blocks
    python tools/scoring_docs.py check      # fail (exit 1) on any divergence

The CI drift check runs `check`. A deliberate mismatch is caught because the
rendered block is produced from the constants, never from the prose: change a
gate in the code and the docs disagree until they are regenerated.
"""
import os
import re
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "app", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from screener.score_wallets import SCORING_SPEC  # noqa: E402

BEGIN_MARKER = "<!-- SCORING-SPEC:BEGIN -->"
END_MARKER = "<!-- SCORING-SPEC:END -->"

DOCS = [
    os.path.join(PROJECT_ROOT, ".agents", "AGENTS.md"),
    os.path.join(PROJECT_ROOT, "README.md"),
]

CONTEXT_MD = os.path.join(PROJECT_ROOT, "CONTEXT.md")


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


def generate() -> None:
    block = render_block()
    for path in DOCS:
        existing, text = _extract_block(path)
        if existing is None:
            # No markers yet: append the block at the end of the file.
            new_text = text.rstrip() + "\n\n" + block
        else:
            new_text = text.replace(existing, block)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
        print(f"[generate] updated {os.path.relpath(path, PROJECT_ROOT)}")


def check(doc_paths=None) -> int:
    """Return 0 when the docs match the code, 1 otherwise.

    `doc_paths` is overridable so the check can be pointed at tampered copies
    in tests — the acceptance criterion for the drift check is that a deliberate
    mismatch fails it, and that must be assertable, not just demonstrable.
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
    print("[check] OK: docs match the code")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        generate()
    else:
        sys.exit(check())
