from __future__ import annotations

import argparse

from .config import build_config_from_args
from .foundation import run_foundation_bootstrap


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-gen",
        description="Foundation CLI for markdown generation pipeline setup.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Source path. Repeat for multiple values.",
    )
    parser.add_argument(
        "--source-list-file",
        action="append",
        default=[],
        help="Text file with one source path per line.",
    )
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--im-temp-dir", default="im-temp")
    parser.add_argument("--md-temp-dir", default="md-temp")
    parser.add_argument("--log-file", default="logs/md-gen.log")
    parser.add_argument(
        "--model-endpoint-url",
        default="http://127.0.0.1:8080/v1/chat/completions",
    )
    parser.add_argument("--model-name", default="lightonocr-2")
    parser.add_argument("--request-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--request-max-retries", type=int, default=2)
    parser.add_argument("--max-longest-edge-px", type=int, default=1540)
    parser.add_argument("--token-threshold", type=int, default=16000)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--overwrite", action="store_true", default=False)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    config = build_config_from_args(args)
    return run_foundation_bootstrap(config)


if __name__ == "__main__":
    raise SystemExit(main())
