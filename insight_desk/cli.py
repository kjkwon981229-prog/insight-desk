from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .domain.models import RunStatus
from .run import execute


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Insight Desk static briefing.")
    parser.add_argument("--config", type=Path, default=Path("config/topics.json"))
    parser.add_argument("--output", type=Path, default=Path("build/site"))
    parser.add_argument("--state-file", type=Path, default=Path("build/run-state.json"))
    parser.add_argument("--cache", type=Path, default=Path(".cache/responses.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state = execute(
        config_path=args.config,
        output_dir=args.output,
        state_path=args.state_file,
        cache_path=args.cache,
    )
    print(f"Insight Desk status: {state.status.value}; publish={str(state.publish).lower()}")
    if state.status in {RunStatus.RENDER_FAILURE, RunStatus.VALIDATION_FAILURE}:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
