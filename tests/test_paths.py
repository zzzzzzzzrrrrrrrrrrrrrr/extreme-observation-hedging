"""Check notebook path discovery independently of a checkout's folder name."""

from contextlib import chdir
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hedging import paths


class ResearchPathsTests(unittest.TestCase):
    def test_nested_notebook_uses_project_metadata_after_move(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "arbitrary-new-folder"
            notebook_dir = root / "notebooks" / "experiments"
            notebook_dir.mkdir(parents=True)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "extreme-observation-hedging"\n', encoding="utf-8"
            )
            # A nested, unrelated Python project must not become our data root.
            (notebook_dir / "pyproject.toml").write_text(
                '[project]\nname = "unrelated"\n', encoding="utf-8"
            )
            with chdir(notebook_dir), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(paths.project_root(), root.resolve())
                self.assertEqual(paths.data_root(), root.resolve() / "data")
                self.assertFalse((root / "data").exists())

    def test_editable_source_fallback_and_explicit_wrong_location(self):
        actual_root = paths.project_root()
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            self.assertEqual(paths.project_root(), actual_root)
            with self.assertRaises(FileNotFoundError):
                paths.project_root(start=directory)

    def test_external_data_directory_is_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory) / "external-data"
            with patch.dict(os.environ, {"HEDGE_DATA_DIR": str(selected)}):
                self.assertEqual(paths.data_root(start="/unrelated"), selected.resolve())
                self.assertFalse(selected.exists())
            with patch.dict(os.environ, {"HEDGE_DATA_DIR": "relative/data"}):
                with self.assertRaisesRegex(ValueError, "absolute"):
                    paths.data_root()


if __name__ == "__main__":
    unittest.main()
