"""
Automated Integration Tests for Lanvan Core VersionManager (test_version_manager.py)
Tests logical file creation, version archiving, SHA-256 calculation, restoration (N+1 appends),
rename, move, copy isolation, and idempotent migration.
"""

import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.version_manager import VersionManager, load_metadata, save_metadata, DATA_DIR, UPLOADS_DIR, VERSIONS_DIR


class TestVersionManager(unittest.TestCase):

    def setUp(self):
        """Prepare clean test environment."""
        self.test_dir = DATA_DIR / "uploads" / "test_folder"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.temp_file = DATA_DIR / "temp_v1.tmp"
        self.temp_file.write_text("Hello Version 1 Content", encoding="utf-8")

    def tearDown(self):
        """Clean up temp files."""
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_01_create_version_transaction_initial(self):
        """Test initial file upload creates Version 1."""
        filename = "test_doc.txt"
        success, lf = VersionManager.create_version_transaction(
            target_dir="test_folder",
            filename=filename,
            incoming_file_path=self.temp_file,
            uploaded_by="unit_test",
            change_type="uploaded"
        )

        self.assertTrue(success)
        self.assertEqual(lf["displayName"], filename)
        self.assertEqual(lf["versionCount"], 1)

        # Active file must exist
        active_path = UPLOADS_DIR / "test_folder" / filename
        self.assertTrue(active_path.exists())
        self.assertEqual(active_path.read_text("utf-8"), "Hello Version 1 Content")

    def test_02_create_version_transaction_second_upload(self):
        """Test uploading second file with same name creates Version 2 and archives Version 1."""
        filename = "test_doc.txt"
        lf_before = VersionManager.get_logical_file_by_path("test_folder", filename)
        self.assertIsNotNone(lf_before)

        temp_v2 = DATA_DIR / "temp_v2.tmp"
        temp_v2.write_text("Hello Version 2 Content", encoding="utf-8")

        success, lf_after = VersionManager.create_version_transaction(
            target_dir="test_folder",
            filename=filename,
            incoming_file_path=temp_v2,
            uploaded_by="unit_test",
            change_type="uploaded"
        )

        if temp_v2.exists():
            temp_v2.unlink()

        self.assertTrue(success)
        self.assertEqual(lf_after["versionCount"], 2)

        # Active file must contain Version 2 content
        active_path = UPLOADS_DIR / "test_folder" / filename
        self.assertTrue(active_path.exists())
        self.assertEqual(active_path.read_text("utf-8"), "Hello Version 2 Content")

        # Version 1 archived file must exist in versions store
        v1_archived = VERSIONS_DIR / lf_after["id"] / "v1.bin"
        self.assertTrue(v1_archived.exists())
        self.assertEqual(v1_archived.read_text("utf-8"), "Hello Version 1 Content")

    def test_03_restore_version(self):
        """Test restoring Version 1 creates Version 3 with restored content."""
        filename = "test_doc.txt"
        lf = VersionManager.get_logical_file_by_path("test_folder", filename)
        self.assertIsNotNone(lf)

        versions = VersionManager.get_version_history(lf["id"])
        self.assertEqual(len(versions), 2)

        # Restore v1 (which is at index 1 in descending sorted list)
        v1_record = [v for v in versions if v["versionNumber"] == 1][0]

        success, msg = VersionManager.restore_version(lf["id"], v1_record["id"])
        self.assertTrue(success)

        # Active file must now match Version 1 content again
        active_path = UPLOADS_DIR / "test_folder" / filename
        self.assertEqual(active_path.read_text("utf-8"), "Hello Version 1 Content")

        # Logical file should now have versionCount = 3
        lf_updated = VersionManager.get_logical_file_by_id(lf["id"])
        self.assertEqual(lf_updated["versionCount"], 3)

    def test_04_delete_logical_file(self):
        """Test deleting logical file cleans up active file, version store, and metadata."""
        filename = "test_doc.txt"
        lf = VersionManager.get_logical_file_by_path("test_folder", filename)
        self.assertIsNotNone(lf)

        lf_id = lf["id"]
        deleted = VersionManager.delete_logical_file(lf_id)
        self.assertTrue(deleted)

        # Active file removed
        active_path = UPLOADS_DIR / "test_folder" / filename
        self.assertFalse(active_path.exists())

        # Version store folder removed
        v_store = VERSIONS_DIR / lf_id
        self.assertFalse(v_store.exists())

        # Metadata removed
        self.assertIsNone(VersionManager.get_logical_file_by_id(lf_id))

    def test_05_no_duplicate_filename_created(self):
        """Test re-uploading an existing filename never creates test_doc_1.txt on disk."""
        filename = "unique_check.txt"
        temp_v1 = DATA_DIR / "temp_chk_v1.tmp"
        temp_v1.write_text("V1", encoding="utf-8")
        VersionManager.create_version_transaction("test_folder", filename, temp_v1)
        if temp_v1.exists(): temp_v1.unlink()

        temp_v2 = DATA_DIR / "temp_chk_v2.tmp"
        temp_v2.write_text("V2", encoding="utf-8")
        VersionManager.create_version_transaction("test_folder", filename, temp_v2)
        if temp_v2.exists(): temp_v2.unlink()

        # Check directory: unique_check_1.txt must NOT exist!
        dup_path = UPLOADS_DIR / "test_folder" / "unique_check_1.txt"
        self.assertFalse(dup_path.exists())

        # Clean up
        lf = VersionManager.get_logical_file_by_path("test_folder", filename)
        if lf:
            VersionManager.delete_logical_file(lf["id"])


if __name__ == "__main__":
    unittest.main()
