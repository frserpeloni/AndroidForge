from __future__ import annotations

import unittest

from sermax_windows_effective_access import (
    EffectiveAccessError,
    _cleanup_resource,
)


class NativeResourceCleanupTests(unittest.TestCase):
    def test_cleanup_failure_does_not_replace_primary_exception(self):
        primary = ValueError("primary failure")
        try:
            raise primary
        except ValueError as caught:
            _cleanup_resource(
                "release failed",
                lambda resource: False,
                object(),
            )
            self.assertIs(caught, primary)
            self.assertTrue(any("release failed" in note for note in caught.__notes__))

    def test_cleanup_failure_without_primary_exception_is_reported(self):
        with self.assertRaisesRegex(EffectiveAccessError, "release failed"):
            _cleanup_resource(
                "release failed",
                lambda resource: False,
                object(),
            )

    def test_cleanup_exception_is_attached_to_primary_exception(self):
        primary = RuntimeError("operation failed")

        def broken_release(resource):
            raise OSError("native release error")

        try:
            raise primary
        except RuntimeError as caught:
            _cleanup_resource("release failed", broken_release, object())
            self.assertIs(caught, primary)
            self.assertTrue(any("native release error" in note for note in caught.__notes__))


if __name__ == "__main__":
    unittest.main()
