import tempfile
import unittest
import zipfile
from pathlib import Path

from hda.db.importer import (
    detect_format,
    format_detected_mismatch,
    normalize_chromosome,
    normalize_genotype,
    parse_23andme,
    parse_ancestrydna,
    parse_myheritage,
)


class ImporterTests(unittest.TestCase):
    FIXTURES_DIR = Path(__file__).parent / "fixtures" / "import"

    def write_text(self, root: Path, name: str, content: str) -> Path:
        path = root / name
        path.write_text(content, encoding="utf-8")
        return path

    def write_zip(self, root: Path, name: str, inner_name: str, content: str) -> Path:
        path = root / name
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(inner_name, content)
        return path

    def test_parse_myheritage_csv(self):
        source = self.FIXTURES_DIR / "myheritage_sample.csv"
        self.assertEqual(detect_format(source), "MyHeritage")
        self.assertEqual(
            parse_myheritage(source),
            [("rs1", "1", 123, "AA"), ("rs2", "X", 456, "CT")],
        )

    def test_parse_23andme_txt_and_zip(self):
        source = self.FIXTURES_DIR / "23andme_sample.txt"
        content = source.read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt = self.write_text(root, "genome.txt", content)
            zipped = self.write_zip(root, "genome.zip", "genome.txt", content)

            self.assertEqual(detect_format(txt), "23andMe")
            self.assertEqual(detect_format(zipped), "23andMe")
            self.assertEqual(
                parse_23andme(txt),
                [("rs10", "1", 111, "AG"), ("rs11", "MT", 222, "--")],
            )
            self.assertEqual(
                parse_23andme(zipped),
                [("rs10", "1", 111, "AG"), ("rs11", "MT", 222, "--")],
            )

    def test_parse_ancestrydna_txt(self):
        source = self.FIXTURES_DIR / "ancestrydna_sample.txt"
        self.assertEqual(detect_format(source), "AncestryDNA")
        self.assertEqual(
            parse_ancestrydna(source),
            [("rs20", "2", 333, "CT"), ("rs21", "Y", 444, "--")],
        )

    def test_normalization_helpers(self):
        self.assertEqual(normalize_chromosome("chr23"), "X")
        self.assertEqual(normalize_chromosome("24"), "Y")
        self.assertEqual(normalize_chromosome("m"), "MT")
        self.assertEqual(normalize_genotype("A", "G"), "AG")
        self.assertEqual(normalize_genotype("--"), "--")
        self.assertEqual(normalize_genotype("0", "0"), "--")

    def test_mismatch_message_is_explicit(self):
        message = format_detected_mismatch(Path("demo.csv"), "23andMe", "MyHeritage")
        self.assertIn("Configured source_format '23andMe' does not match", message)
        self.assertIn("which looks like 'MyHeritage'", message)
        self.assertIn("config.yaml", message)

    def test_unknown_fixture_is_reported_as_unknown(self):
        source = self.FIXTURES_DIR / "malformed_unknown.txt"
        self.assertEqual(detect_format(source), "unknown")


if __name__ == "__main__":
    unittest.main()
