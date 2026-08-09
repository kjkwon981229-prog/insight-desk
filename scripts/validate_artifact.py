from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insight_desk.web.validate import validate_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an Insight Desk Pages artifact.")
    parser.add_argument("site_dir", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.site_dir)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"artifact valid: {args.site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
