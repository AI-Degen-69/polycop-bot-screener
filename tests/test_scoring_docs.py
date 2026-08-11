#!/usr/bin/env python3
"""The documentation drift check: docs are generated from the code's constants,
so a value changed in the code must surface as a failing check until the docs
are regenerated. These prove the check can fail — the acceptance criterion for
ticket #11 was that a deliberate mismatch fails it.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))
from paths import PROJECT_ROOT

import scoring_docs  # noqa: E402


class TestRenderedBlockComesFromTheCode(unittest.TestCase):
    def test_the_block_contains_the_code_gate_value(self):
        # The rendered block is produced from SCORING_SPEC, never from prose.
        block = scoring_docs.render_block()
        self.assertIn("$200", block)          # whale gate
        self.assertIn("5.0% modelled", block)  # slippage gate
        self.assertIn("&ge; 80", block)        # re-measured S-Tier floor (ADR 0010)

    def test_the_block_uses_the_modelled_copy_pnl_term(self):
        # The gate condition renders CONTEXT.md's approved term, not the
        # avoided "backtest copy PnL" / "copy PnL" (issue #27).
        block = scoring_docs.render_block()
        self.assertIn("Modelled Copy PnL", block)

    def test_the_block_contains_the_simulated_verdict_bands(self):
        # The verdict bands (ADR 0002) are rendered from the same constants
        # assign_simulated_tier reads, never from prose.
        block = scoring_docs.render_block()
        self.assertIn("Simulated Verdict Tier Bands", block)
        self.assertIn("&ge; 0.85", block)  # simulated S-Tier floor
        self.assertIn("&ge; 0.30", block)  # simulated C-Tier floor


class TestTheCheckFailsOnADeliberateMismatch(unittest.TestCase):
    """The proof demanded by the ticket: corrupt a doc and the check fails."""

    def _tampered_doc(self, tampered_block=None):
        tmp = tempfile.mkdtemp()
        doc = os.path.join(tmp, "AGENTS.md")
        content = tampered_block or scoring_docs.render_block().replace("$200", "$999")
        with open(doc, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(shutil.rmtree, tmp)
        return doc

    def test_a_changed_gate_value_fails_the_check(self):
        doc = self._tampered_doc()
        # The check itself must fail against a doc whose gate value disagrees
        # with the code — not merely that the extracted text differs.
        self.assertEqual(scoring_docs.check([doc]), 1)

    def test_a_matching_doc_passes_the_check(self):
        doc = self._tampered_doc(tampered_block=scoring_docs.render_block())
        self.assertEqual(scoring_docs.check([doc]), 0)

    def test_a_missing_block_is_detected(self):
        doc = self._tampered_doc(tampered_block="# nothing here\n")
        self.assertEqual(scoring_docs.check([doc]), 1)


class TestWebUiLabelsAreRenderedFromTheCode(unittest.TestCase):
    """The tier floors and gem threshold embedded in the web UI are rendered
    from the same constants as the markdown tables, so a band recalibration
    cannot silently leave a stale label on the page.
    """

    def test_the_shipped_assets_carry_the_rendered_labels(self):
        self.assertEqual(
            scoring_docs.check_ui(), [],
            "every UI label must match the SCORING_SPEC constants",
        )

    def test_each_label_entry_has_a_matching_expected_and_pattern(self):
        for label in scoring_docs.UI_LABELS:
            with self.subTest(description=label["description"]):
                path = os.path.join(PROJECT_ROOT, label["relpath"])
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                # The pattern must locate the current expected value, so that
                # `generate` can swap a stale number for the rendered one.
                self.assertRegex(text, label["pattern"])
                self.assertIn(label["expected"], text)

    def _stale_variant(self, entry):
        """A label entry's expected string with its value swapped to 99, so a
        tamper stays meaningful no matter what the constants currently are."""
        return re.sub(r"\d+", "99", entry["expected"])

    def _label(self, description):
        """The UI_LABELS entry whose description matches, found by name so the
        tamper tests do not depend on list order."""
        return next(
            label for label in scoring_docs.UI_LABELS
            if label["description"] == description
        )

    def _tamper_ui(self, entry, tampered_text):
        """Write `tampered_text` into a temp copy of the entry's file and check
        the drift check against that copy."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        doc = os.path.join(tmp, os.path.basename(entry["relpath"]))
        with open(doc, "w", encoding="utf-8") as f:
            f.write(tampered_text)
        return scoring_docs.check(ui_overrides={entry["relpath"]: doc})

    def _read_real(self, relpath):
        with open(os.path.join(PROJECT_ROOT, relpath), "r", encoding="utf-8") as f:
            return f.read()

    def test_a_stale_stat_pill_label_fails_the_check(self):
        entry = self._label("S-Tier stat pill floor")
        tampered = self._read_real(entry["relpath"]).replace(
            entry["expected"], self._stale_variant(entry)
        )
        self.assertEqual(self._tamper_ui(entry, tampered), 1)

    def test_a_stale_gem_tooltip_label_fails_the_check(self):
        entry = self._label("gem tooltip site-score ceiling")
        tampered = self._read_real(entry["relpath"]).replace(
            entry["expected"], self._stale_variant(entry)
        )
        self.assertEqual(self._tamper_ui(entry, tampered), 1)

    def test_a_stale_gate_tooltip_value_fails_the_check(self):
        entry = self._label("Profit/Loss gate tooltip value")
        tampered = self._read_real(entry["relpath"]).replace(
            entry["expected"], self._stale_variant(entry)
        )
        self.assertEqual(self._tamper_ui(entry, tampered), 1)

    def test_a_stale_bankroll_label_fails_the_check(self):
        entry = self._label("copy bankroll phrase")
        tampered = self._read_real(entry["relpath"]).replace(
            entry["expected"], self._stale_variant(entry)
        )
        self.assertEqual(self._tamper_ui(entry, tampered), 1)

    def test_a_stale_gate_count_fails_the_check(self):
        entry = self._label("hard rejection gate count (gem tooltip)")
        tampered = self._read_real(entry["relpath"]).replace(
            entry["expected"], self._stale_variant(entry)
        )
        self.assertEqual(self._tamper_ui(entry, tampered), 1)

    def test_a_stale_duplicate_in_the_same_format_fails_the_check(self):
        # The expected string still exists (so a plain substring check would
        # pass), but a second label in the same format carries a stale value.
        entry = self._label("S-Tier stat pill floor")
        tampered = self._read_real(entry["relpath"]).replace(
            entry["expected"],
            entry["expected"] + " " + self._stale_variant(entry),
        )
        self.assertEqual(self._tamper_ui(entry, tampered), 1)


class TestGenerateIsIdempotent(unittest.TestCase):
    """generate() on a synced tree must be a byte-level no-op, and a fresh doc
    must settle on the very first run — the regression this locks in is a
    generator that appended one newline past the END marker every run.
    """

    def _ui_copies(self, tmp):
        ui_overrides = {}
        for label in scoring_docs.UI_LABELS:
            if label["relpath"] in ui_overrides:
                continue
            src = os.path.join(PROJECT_ROOT, label["relpath"])
            dst = os.path.join(tmp, os.path.basename(label["relpath"]))
            shutil.copy(src, dst)
            ui_overrides[label["relpath"]] = dst
        return ui_overrides

    def test_generate_is_a_noop_on_a_synced_tree(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        ui_overrides = self._ui_copies(tmp)
        docs = []
        for relpath in (".agents/AGENTS.md", "README.md"):
            src = os.path.join(PROJECT_ROOT, relpath)
            dst = os.path.join(tmp, os.path.basename(relpath))
            shutil.copy(src, dst)
            docs.append(dst)
        before = {
            p: open(p, encoding="utf-8").read()
            for p in docs + list(ui_overrides.values())
        }
        scoring_docs.generate(doc_paths=docs, ui_overrides=ui_overrides)
        for path, content in before.items():
            with self.subTest(path=os.path.basename(path)):
                with open(path, encoding="utf-8") as f:
                    self.assertEqual(f.read(), content)

    def test_generate_settles_a_fresh_doc_on_the_first_run(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        ui_overrides = self._ui_copies(tmp)
        doc = os.path.join(tmp, "FRESH.md")
        with open(doc, "w", encoding="utf-8") as f:
            f.write("# Fresh doc\n\nIntro text.\n")
        scoring_docs.generate(doc_paths=[doc], ui_overrides=ui_overrides)
        first = open(doc, encoding="utf-8").read()
        scoring_docs.generate(doc_paths=[doc], ui_overrides=ui_overrides)
        with open(doc, encoding="utf-8") as f:
            self.assertEqual(f.read(), first)


class TestContextMdStaysThresholdFree(unittest.TestCase):
    def test_the_context_glossary_has_no_numeric_values(self):
        with open(os.path.join(PROJECT_ROOT, "CONTEXT.md"), "r", encoding="utf-8") as f:
            text = f.read()
        self.assertNotRegex(
            text,
            r"\d",
            "CONTEXT.md is a domain glossary and must stay free of thresholds, "
            "weights and gate values; a number here would drift independently of the code",
        )


if __name__ == "__main__":
    unittest.main()
