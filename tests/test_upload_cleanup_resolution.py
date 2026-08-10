"""Regression tests for upload path resolution and cancellation cleanup."""

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.upload_path_resolver import UploadPathResolver
import app.routers.files as files_module


class TestUploadCleanupResolution(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_root.cleanup)

        self.uploads_dir = Path(self.temp_root.name) / "data" / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.temp_chunks_dir = Path(self.temp_root.name) / "data" / "temp_chunks"
        self.temp_chunks_dir.mkdir(parents=True, exist_ok=True)

        self._original_upload_folder = files_module.UPLOAD_FOLDER
        self._original_temp_chunks_folder = files_module.TEMP_CHUNKS_FOLDER
        files_module.UPLOAD_FOLDER = self.uploads_dir
        files_module.TEMP_CHUNKS_FOLDER = self.temp_chunks_dir

    def tearDown(self):
        files_module.UPLOAD_FOLDER = self._original_upload_folder
        files_module.TEMP_CHUNKS_FOLDER = self._original_temp_chunks_folder

    def _write_file(self, relative_path: str, content: str = "x") -> Path:
        target = self.uploads_dir / Path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def test_cleanup_nested_file_does_not_delete_root_same_name(self):
        root_file = self._write_file("test.txt", "root")
        root_tmp = self._write_file("test.txt.tmp", "root tmp")
        nested_file = self._write_file("Lot of files/test.txt", "nested")
        nested_tmp = self._write_file("Lot of files/test.txt.tmp", "nested tmp")
        nested_chunk_tmp = self._write_file("Lot of files/test.txt.chunk.tmp", "nested chunk")

        deleted = files_module.cleanup_temp_file_for_filename(
            "test.txt",
            parent_path="Lot of files",
            upload_id="upload-123",
            relative_path="Lot of files/test.txt",
        )

        self.assertEqual(deleted, 3)
        self.assertTrue(root_file.exists())
        self.assertTrue(root_tmp.exists())
        self.assertFalse(nested_file.exists())
        self.assertFalse(nested_tmp.exists())
        self.assertFalse(nested_chunk_tmp.exists())

    def test_cleanup_root_file_does_not_delete_nested_same_name(self):
        root_file = self._write_file("test.txt", "root")
        root_tmp = self._write_file("test.txt.tmp", "root tmp")
        nested_file = self._write_file("Lot of files/test.txt", "nested")
        nested_tmp = self._write_file("Lot of files/test.txt.tmp", "nested tmp")

        deleted = files_module.cleanup_temp_file_for_filename(
            "test.txt",
            parent_path="",
            upload_id="upload-root",
            relative_path="test.txt",
        )

        self.assertEqual(deleted, 2)
        self.assertFalse(root_file.exists())
        self.assertFalse(root_tmp.exists())
        self.assertTrue(nested_file.exists())
        self.assertTrue(nested_tmp.exists())

    def test_cleanup_is_idempotent_for_duplicate_requests(self):
        root_file = self._write_file("test.txt", "root")
        nested_file = self._write_file("Lot of files/test.txt", "nested")

        first = files_module.cleanup_temp_file_for_filename(
            "test.txt",
            parent_path="Lot of files",
            upload_id="upload-dup",
            relative_path="Lot of files/test.txt",
        )
        second = files_module.cleanup_temp_file_for_filename(
            "test.txt",
            parent_path="Lot of files",
            upload_id="upload-dup",
            relative_path="Lot of files/test.txt",
        )

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertTrue(root_file.exists())
        self.assertFalse(nested_file.exists())

    def test_upload_path_resolver_distinguishes_same_filename_across_folders(self):
        root = UploadPathResolver.resolve("", "test.txt", self.uploads_dir)
        nested = UploadPathResolver.resolve("Lot of files", "test.txt", self.uploads_dir)

        self.assertEqual(root.full_path, self.uploads_dir / "test.txt")
        self.assertEqual(nested.full_path, self.uploads_dir / "Lot of files" / "test.txt")
        self.assertNotEqual(root.full_path, nested.full_path)

    def test_upload_path_resolver_rejects_traversal_and_absolute_paths(self):
        bad_cases = [
            ("../escape", "test.txt"),
            ("Lot of files", "../test.txt"),
            ("..", "test.txt"),
            ("", r"C:\\escape.txt"),
            ("", r"\\\\server\\share\\escape.txt"),
        ]

        for parent_path, filename in bad_cases:
            with self.assertRaises(HTTPException):
                UploadPathResolver.resolve(parent_path, filename, self.uploads_dir)


if __name__ == "__main__":
    unittest.main()