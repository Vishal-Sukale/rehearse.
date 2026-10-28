"""Resume text extraction (no third-party packages needed for the TXT path)."""
import unittest

from interviewer.resume import MAX_BYTES, ResumeError, extract_text

GOOD = ("Asha Verma\nBackend Engineer\n" + "Built payment services in Python and PostgreSQL, reducing p99 latency by 40%. " * 3).encode()


class ExtractTextTests(unittest.TestCase):
    def test_reads_txt_and_collapses_whitespace(self):
        text = extract_text("cv.txt", GOOD + b"\n\n\n\n\nMore    spaces")
        self.assertIn("p99 latency", text)
        self.assertNotIn("\n\n\n", text)
        self.assertNotIn("    ", text)

    def test_too_short_is_rejected(self):
        with self.assertRaises(ResumeError):
            extract_text("cv.txt", b"hi")

    def test_unsupported_type(self):
        with self.assertRaises(ResumeError):
            extract_text("cv.exe", GOOD)

    def test_too_large(self):
        with self.assertRaises(ResumeError):
            extract_text("cv.txt", b"x" * (MAX_BYTES + 1))

    def test_text_is_capped(self):
        self.assertLessEqual(len(extract_text("cv.txt", b"word " * 20000)), 14000)


if __name__ == "__main__":
    unittest.main()