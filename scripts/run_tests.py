from __future__ import annotations

"""Run the historical regression corpus against a deterministic wall clock.

The corpus contains captured live fixtures with day-only dates such as ``23일`` whose target is
not freshness. Running those fixtures against the machine's real date makes unrelated tests decay
as calendar time advances. Freeze only the unittest process to the last canonical pre-326 test
reference date. Production processes are untouched, and tests whose target is freshness should
continue to pass an explicit ``now`` to the shared admission APIs.
"""

import datetime as datetime_module
from datetime import datetime as RealDateTime, timezone
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_REFERENCE_NOW = RealDateTime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class FrozenTestDateTime(RealDateTime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return TEST_REFERENCE_NOW.replace(tzinfo=None)
        return TEST_REFERENCE_NOW.astimezone(tz)

    @classmethod
    def utcnow(cls):
        return TEST_REFERENCE_NOW.replace(tzinfo=None)


def main() -> int:
    # Apply before discovery so modules using ``from datetime import datetime`` bind
    # the deterministic subclass. This process runs tests only; no production entrypoint
    # imports or executes this runner.
    datetime_module.datetime = FrozenTestDateTime
    suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
