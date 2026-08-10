#!/usr/bin/env python3
"""The documentation drift check: docs are generated from the code's constants,
so a value changed in the code must surface as a failing check until the docs
are regenerated. These prove the check can fail — the acceptance criterion for
ticket #11 was that a deliberate mismatch fails it.
"""
import os
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(PROJECT_ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))

import scoring_docs  # noqa: E402


class TestRenderedBlockComesFromTheCode(unittest.TestCase):
    def test_the_block_contains_the_code_gate_value(self):
        # The rendered block is produced from SCORING_SPEC, never from prose.
        block = scoring_docs.render_block()
        self.assertIn("$200", block)          # whale gate
        self.assertIn("5.0% modelled", block)  # slippage gate
        self.assertIn("&ge; 72", block)        # recalibrated S-Tier floor


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
