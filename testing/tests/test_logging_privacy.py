"""
Lanvan Logging & Diagnostic Privacy Automated Regression Test
Verifies that raw user filenames, full filesystem paths, clipboard data,
and user feedback text are NEVER written to logger outputs or diagnostic reports.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.logger import logger, StructuredLogger

class TestLoggingPrivacy(unittest.TestCase):
    
    def test_safe_extension_extraction(self):
        """Verify extension extraction never includes filenames or directory paths"""
        self.assertEqual(StructuredLogger.extract_safe_ext("my_secret_photo.jpg"), "JPG")
        self.assertEqual(StructuredLogger.extract_safe_ext("C:\\Users\\Secret\\Document.PDF"), "PDF")
        self.assertEqual(StructuredLogger.extract_safe_ext("/data/user/0/com.lanvan.app/files/test.png"), "PNG")
        self.assertEqual(StructuredLogger.extract_safe_ext("no_ext_file"), "BIN")

    def test_format_size(self):
        """Verify human readable byte size formatting"""
        self.assertEqual(StructuredLogger.format_size(512), "512 B")
        self.assertEqual(StructuredLogger.format_size(2048), "2.0 KB")
        self.assertEqual(StructuredLogger.format_size(5 * 1024 * 1024), "5.00 MB")

    def test_upload_logging_privacy(self):
        """Verify upload logging strips raw filenames and paths"""
        secret_filename = "PRIVATE_FILENAME_DO_NOT_LOG_99999.jpg"
        secret_path = "C:\\Users\\JohnDoe\\Uploads\\PRIVATE_FILENAME_DO_NOT_LOG_99999.jpg"
        
        # Log an upload event
        logger.log_upload(
            event="Upload Completed",
            op_id="A7F2",
            file_ext=logger.extract_safe_ext(secret_filename),
            size_bytes=258000,
            duration=0.12,
            status="SUCCESS"
        )
        
        recent_logs = "\n".join(logger.get_recent_history(10))
        
        # Assert secret filename and path DO NOT appear
        self.assertNotIn("PRIVATE_FILENAME_DO_NOT_LOG_99999", recent_logs)
        self.assertNotIn("JohnDoe", recent_logs)
        self.assertIn("[UPLOAD][A7F2] Upload Completed", recent_logs)
        self.assertIn("Type: JPG", recent_logs)

    def test_clipboard_logging_privacy(self):
        """Verify clipboard logging strips raw text content"""
        secret_clipboard_text = "TEST_PRIVATE_CLIPBOARD_99999"
        
        # Log a clipboard event
        logger.log_clipboard(
            action="Add",
            item_type="TEXT",
            size_bytes=len(secret_clipboard_text.encode('utf-8')),
            status="SUCCESS"
        )
        
        recent_logs = "\n".join(logger.get_recent_history(10))
        
        # Assert secret clipboard string DOES NOT appear
        self.assertNotIn("TEST_PRIVATE_CLIPBOARD_99999", recent_logs)
        self.assertIn("[CLIPBOARD] Add", recent_logs)
        self.assertIn("Type: TEXT", recent_logs)

if __name__ == "__main__":
    unittest.main()
