import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hda.api import annotator
from hda.db.schema import init_db


class DummyAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class AnnotatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "alice.db"
        init_db(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    async def test_annotate_snp_uses_cache_when_available(self):
        fetch = AsyncMock(
            return_value={
                "rsid": "rs123",
                "source": "snpedia",
                "gene": "GENE1",
                "summary": "Cached summary",
            }
        )

        with patch("hda.api.annotator.get_db_path", return_value=self.db_path), patch(
            "hda.api.annotator.httpx.AsyncClient", return_value=DummyAsyncClient()
        ), patch("hda.api.annotator.snpedia.fetch_snp", fetch):
            first = await annotator.annotate_snp("rs123", subject="alice", sources=["snpedia"])

        self.assertEqual(first["summary"], "Cached summary")
        self.assertEqual(fetch.await_count, 1)

        fetch_again = AsyncMock(side_effect=AssertionError("network fetch should not run on cache hit"))
        with patch("hda.api.annotator.get_db_path", return_value=self.db_path), patch(
            "hda.api.annotator.httpx.AsyncClient", return_value=DummyAsyncClient()
        ), patch("hda.api.annotator.snpedia.fetch_snp", fetch_again):
            second = await annotator.annotate_snp("rs123", subject="alice", sources=["snpedia"])

        self.assertEqual(second["summary"], "Cached summary")
        self.assertEqual(second["sources"], ["snpedia"])

    async def test_force_refresh_bypasses_cache_and_replaces_annotation(self):
        with patch("hda.api.annotator.get_db_path", return_value=self.db_path), patch(
            "hda.api.annotator.httpx.AsyncClient", return_value=DummyAsyncClient()
        ), patch(
            "hda.api.annotator.snpedia.fetch_snp",
            AsyncMock(
                return_value={
                    "rsid": "rs123",
                    "source": "snpedia",
                    "gene": "GENE1",
                    "summary": "Old summary",
                }
            ),
        ):
            await annotator.annotate_snp("rs123", subject="alice", sources=["snpedia"])

        refresh_fetch = AsyncMock(
            return_value={
                "rsid": "rs123",
                "source": "snpedia",
                "gene": "GENE1",
                "summary": "Fresh summary",
            }
        )
        with patch("hda.api.annotator.get_db_path", return_value=self.db_path), patch(
            "hda.api.annotator.httpx.AsyncClient", return_value=DummyAsyncClient()
        ), patch("hda.api.annotator.snpedia.fetch_snp", refresh_fetch):
            refreshed = await annotator.annotate_snp(
                "rs123", subject="alice", sources=["snpedia"], force_refresh=True
            )

        self.assertEqual(refreshed["summary"], "Fresh summary")
        self.assertEqual(refresh_fetch.await_count, 1)

    async def test_annotate_snp_merges_available_sources_and_ignores_failures(self):
        with patch("hda.api.annotator.get_db_path", return_value=self.db_path), patch(
            "hda.api.annotator.httpx.AsyncClient", return_value=DummyAsyncClient()
        ), patch(
            "hda.api.annotator.snpedia.fetch_snp",
            AsyncMock(
                return_value={
                    "rsid": "rs999",
                    "source": "snpedia",
                    "gene": "GENE9",
                    "summary": "SNPedia summary",
                }
            ),
        ), patch(
            "hda.api.annotator.ensembl.fetch_snp",
            AsyncMock(side_effect=RuntimeError("upstream failure")),
        ):
            result = await annotator.annotate_snp(
                "rs999", subject="alice", sources=["snpedia", "ensembl"]
            )

        self.assertEqual(result["gene"], "GENE9")
        self.assertEqual(result["summary"], "SNPedia summary")
        self.assertEqual(result["sources"], ["snpedia"])


if __name__ == "__main__":
    unittest.main()
