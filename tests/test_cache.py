import tempfile
import unittest

from ploymarket_sim.cache import CachePolicy, JsonCache


class CacheTests(unittest.TestCase):
    def test_returns_fresh_cached_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = JsonCache(CachePolicy(True, directory, 60, True))
            cache.set("https://example.com/data?a=1", {"ok": True})

            self.assertEqual(cache.get_fresh("https://example.com/data?a=1"), {"ok": True})

    def test_disabled_cache_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = JsonCache(CachePolicy(False, directory, 60, True))
            cache.set("https://example.com/data?a=1", {"ok": True})

            self.assertIsNone(cache.get_fresh("https://example.com/data?a=1"))

    def test_reports_cache_stats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = JsonCache(CachePolicy(True, directory, 60, True))
            cache.set("https://example.com/data?a=1", {"ok": True})

            stats = cache.stats()

            self.assertTrue(stats.enabled)
            self.assertEqual(stats.file_count, 1)
            self.assertGreater(stats.total_bytes, 0)
