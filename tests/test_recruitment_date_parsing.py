import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.domain.recruitment.csv_import import _parse_date


class RecruitmentDateParsingTests(unittest.TestCase):
    def test_excel_serial_update_date(self):
        self.assertEqual(str(_parse_date("46315")), "2026-10-20")

    def test_text_date_is_unchanged(self):
        self.assertEqual(str(_parse_date("2026/10/21")), "2026-10-21")


if __name__ == "__main__":
    unittest.main()
