#!/usr/bin/env python3
"""The paths module owns the repo layout and the dataset inventory.

Every directory and dataset filename is derived in one place
(app/src/paths.py), so a renamed file or a moved directory cannot split the
pipeline's writers from its readers. These tests pin that contract: the
constants resolve to real locations, a cache reset clears the whole dataset
including the feed the page reads, and no app/src module re-creates its own
path bootstrap or hardcodes a dataset filename where the constant should be
used.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "src"))

from paths import (  # noqa: E402
    APP_DIR,
    DATA_DIR,
    PHASE1_FILE,
    PHASE2_FILE,
    PHASE3_FILE,
    PROJECT_ROOT,
    SRC_DIR,
    TOOLS_DIR,
    WEB_DIR,
)


def _app_src_py_files():
    for root, _dirs, files in os.walk(SRC_DIR):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


class TestPathsResolve(unittest.TestCase):
    def test_every_directory_constant_points_at_a_real_directory(self):
        for label, path in (
            ("PROJECT_ROOT", PROJECT_ROOT), ("APP_DIR", APP_DIR),
            ("SRC_DIR", SRC_DIR), ("WEB_DIR", WEB_DIR),
            ("DATA_DIR", DATA_DIR), ("TOOLS_DIR", TOOLS_DIR),
        ):
            with self.subTest(label=label):
                self.assertTrue(os.path.isdir(path), f"{label} -> {path}")

    def test_the_data_dir_is_app_data(self):
        self.assertEqual(DATA_DIR, os.path.join(APP_DIR, "data"))

    def test_the_phase_files_are_distinct(self):
        self.assertEqual(len({PHASE1_FILE, PHASE2_FILE, PHASE3_FILE}), 3)

    def test_importing_paths_makes_the_tools_package_importable(self):
        """The server imports `tools.measure_latency_slippage` by package
        name after chdir'ing into app/web, where the repo root is no longer
        the cwd. That needs PROJECT_ROOT on sys.path — `tools` is a package
        under the repo root, so inserting TOOLS_DIR itself would look for
        tools/tools/x and fail."""
        self.assertIn(PROJECT_ROOT, sys.path)
        import importlib
        tools_mod = importlib.import_module("tools.measure_latency_slippage")
        self.assertTrue(hasattr(tools_mod, "discover_markets"))


class TestACacheResetClearsTheWholeDataset(unittest.TestCase):
    def test_reset_data_cache_deletes_every_phase_file_including_the_feed(self):
        """Clear Data must actually clear the data the page shows. The page
        reads the phase3 feed (via /api/feed/v1), so a reset that stops at
        the pre-feed phase files deletes files nothing renders, then the
        reload refills the grid from the untouched feed — the button visibly
        does nothing. All three phase files must go, so the next fetch 404s
        and the page shows its empty state."""
        from pipeline.reset_data_cache import FILES_TO_REMOVE

        self.assertEqual(
            FILES_TO_REMOVE,
            [
                os.path.join(DATA_DIR, PHASE1_FILE),
                os.path.join(DATA_DIR, PHASE2_FILE),
                os.path.join(DATA_DIR, PHASE3_FILE),
            ],
        )
        self.assertIn("phase3", os.path.basename(FILES_TO_REMOVE[-1]))

    def test_screen_checks_the_same_file_phase3_writes(self):
        """screen.py's staleness file is the constant phase3 writes, not a
        second spelling of the name."""
        screen_src = open(os.path.join(PROJECT_ROOT, "screen.py"), encoding="utf-8").read()
        self.assertIn("PHASE3_FILE", screen_src)
        self.assertNotIn('"phase3_simulated_targets.json"', screen_src)


class TestNoPathBootstrapDrift(unittest.TestCase):
    """The friction the refactor removed: every module re-derived the repo
    layout and restated the dataset filenames. These guard the removal from
    quietly growing an eleventh copy."""

    CANONICAL_INSERT = "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))"

    def test_every_app_src_sys_path_insert_is_canonical_or_paths_own(self):
        # Scope is app/src only: screen.py and tools/scoring_docs.py run from
        # the repo root and carry their own one-line inserts, covered by
        # test_the_root_entry_scripts_import_the_inventory_from_paths below.
        for path in _app_src_py_files():
            if os.path.basename(path) == "paths.py":
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if "sys.path.insert" in line:
                        self.assertEqual(
                            line.strip(), self.CANONICAL_INSERT,
                            f"{path}: a module re-created its own path bootstrap",
                        )

    def test_no_app_src_module_hardcodes_a_dataset_filename(self):
        for path in _app_src_py_files():
            if os.path.basename(path) == "paths.py":
                continue
            text = open(path, encoding="utf-8").read()
            for match in re.finditer(r'os\.path\.join\(DATA_DIR, "phase[123]_', text):
                self.fail(f"{path}: hardcoded dataset filename {match.group()!r}")

    def test_any_module_using_data_dir_imports_it_from_paths(self):
        for path in _app_src_py_files():
            if os.path.basename(path) == "paths.py":
                continue
            text = open(path, encoding="utf-8").read()
            if "DATA_DIR" in text and "from paths import" not in text:
                self.fail(f"{path}: derives DATA_DIR without importing it from paths")

    def test_the_root_entry_scripts_import_the_inventory_from_paths(self):
        for rel in ("screen.py", os.path.join("tools", "scoring_docs.py")):
            with self.subTest(rel=rel):
                src = open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8").read()
                self.assertIn("from paths import", src)


if __name__ == "__main__":
    unittest.main()
