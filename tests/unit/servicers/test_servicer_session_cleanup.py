import concurrent.futures
import glob
import os
import unittest
from unittest.mock import MagicMock, patch

from app.shared.core.database import get_db_session


class TestServicerSessionCleanup(unittest.TestCase):
    def test_no_next_generator_in_servicers(self):
        """Verify that no servicer or consumer uses next(session_gen) pattern."""
        service_dirs = glob.glob("Services/*/src")
        for s_dir in service_dirs:
            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.endswith(".py"):
                        file_path = os.path.join(root, f)
                        with open(file_path, "r", encoding="utf-8") as src_f:
                            content = src_f.read()
                            self.assertNotIn(
                                "next(session_gen)",
                                content,
                                f"Leak pattern next(session_gen) found in {file_path}",
                            )
                            self.assertNotIn(
                                "= next(get_session())",
                                content,
                                f"Leak pattern next(get_session()) found in {file_path}",
                            )

    def test_get_db_session_context_manager_cleanup(self):
        """Verify get_db_session context manager commits and closes cleanly."""
        mock_session = MagicMock()
        with patch("app.shared.core.database.SessionLocal", return_value=mock_session):
            with get_db_session() as db:
                self.assertEqual(db, mock_session)
            
            mock_session.commit.assert_called_once()
            mock_session.expunge_all.assert_called_once()
            mock_session.close.assert_called_once()

    def test_get_db_session_context_manager_rollback_on_exception(self):
        """Verify get_db_session rolls back and closes on exception."""
        mock_session = MagicMock()
        with patch("app.shared.core.database.SessionLocal", return_value=mock_session):
            with self.assertRaises(ValueError):
                with get_db_session() as db:
                    raise ValueError("Simulated handler error")
            
            mock_session.rollback.assert_called_once()
            mock_session.expunge_all.assert_called_once()
            mock_session.close.assert_called_once()

    def test_100_concurrent_session_acquisitions(self):
        """Verify 100 concurrent context manager sessions release cleanly without pool depletion."""
        closed_count = 0

        def run_worker(_):
            nonlocal closed_count
            mock_session = MagicMock()
            with patch("app.shared.core.database.SessionLocal", return_value=mock_session):
                with get_db_session() as db:
                    _ = db
            if mock_session.close.called:
                closed_count += 1
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(run_worker, range(100)))

        self.assertEqual(len(results), 100)
        self.assertTrue(all(results))
        self.assertEqual(closed_count, 100)


if __name__ == "__main__":
    unittest.main()
