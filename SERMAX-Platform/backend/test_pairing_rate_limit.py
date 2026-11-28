"""Testes do limitador de janela deslizante."""
import unittest

from pairing_rate_limit import SlidingWindowRateLimiter


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


if __name__ == "__main__":
    unittest.main()
