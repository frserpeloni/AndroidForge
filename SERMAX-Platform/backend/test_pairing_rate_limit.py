"""Testes do limitador de janela deslizante."""
import unittest

from pairing_rate_limit import SlidingWindowRateLimiter, SQLiteSlidingWindowRateLimiter


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_blocks_after_limit_inside_window(self):
        now = [100.0]
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10, clock=lambda: now[0])
        self.assertTrue(limiter.allow("peer-a"))
        self.assertTrue(limiter.allow("peer-a"))
        self.assertFalse(limiter.allow("peer-a"))

    def test_expired_events_do_not_block_new_attempts(self):
        now = [100.0]
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=5, clock=lambda: now[0])
        self.assertTrue(limiter.allow("peer-a"))
        now[0] = 105.1
        self.assertTrue(limiter.allow("peer-a"))

    def test_keys_have_independent_buckets(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=10, clock=lambda: 100.0)
        self.assertTrue(limiter.allow("reserve:peer-a"))
        self.assertTrue(limiter.allow("finalize:peer-a"))
        self.assertFalse(limiter.allow("reserve:peer-a"))

    def test_rejects_invalid_configuration_and_key(self):
        with self.assertRaises(ValueError):
            SlidingWindowRateLimiter(limit=0)
        limiter = SlidingWindowRateLimiter()
        with self.assertRaises(ValueError):
            limiter.allow("")

    def test_reset_clears_all_buckets(self):
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=10, clock=lambda: 100.0)
        self.assertTrue(limiter.allow("peer-a"))
        limiter.reset()
        self.assertTrue(limiter.allow("peer-a"))


    def test_sqlite_limiter_persists_across_instances_and_expires(self):
        import tempfile
        from pathlib import Path

        now = [100.0]
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "security.sqlite3")
            first = SQLiteSlidingWindowRateLimiter(
                limit=2, window_seconds=10, clock=lambda: now[0]
            )
            second = SQLiteSlidingWindowRateLimiter(
                limit=2, window_seconds=10, clock=lambda: now[0]
            )
            self.assertTrue(first.allow("reserve:proxy", db))
            self.assertTrue(second.allow("reserve:proxy", db))
            self.assertFalse(first.allow("reserve:proxy", db))
            now[0] = 110.1
            self.assertTrue(second.allow("reserve:proxy", db))

    def test_sqlite_limiter_is_atomic_under_concurrent_attempts(self):
        import tempfile
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "security.sqlite3")
            limit = 5
            limiters = [
                SQLiteSlidingWindowRateLimiter(limit=limit, window_seconds=60)
                for _ in range(12)
            ]
            def attempt(index):
                return limiters[index % len(limiters)].allow("reserve:shared-proxy", db)

            with ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(attempt, range(24)))

            self.assertEqual(sum(results), limit)

    def test_sqlite_limiter_keeps_operation_buckets_separate(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "security.sqlite3")
            limiter = SQLiteSlidingWindowRateLimiter(limit=1, clock=lambda: 100.0)
            self.assertTrue(limiter.allow("reserve:proxy", db))
            self.assertTrue(limiter.allow("finalize:proxy", db))
            self.assertFalse(limiter.allow("reserve:proxy", db))


if __name__ == "__main__":
    unittest.main()
