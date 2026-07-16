from __future__ import annotations

import argparse
from types import SimpleNamespace

from common.config import ConfigValidationError, build_config_from_args
from common.config_dump import format_config_dump
from .foundation import run_foundation_bootstrap

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-gen",
        description="Foundation CLI for markdown generation pipeline setup.",
    )

    parser.add_argument("--source", required=True, help="Source directory containing top-level input files.")
    parser.add_argument("--output", required=True, help="Output directory root for generated artifacts.")
    parser.add_argument( "--summary-prompt", default=None, help="Optional path to a summary system prompt file.", )

    parser.add_argument("--ocr-model-endpoint", default=None)
    parser.add_argument("--ocr-model-name", default=None)
    parser.add_argument("--ocr-timeout-seconds", type=float, default=None)
    parser.add_argument("--ocr-max-retries", type=int, default=None)

    parser.add_argument("--language-model-endpoint", default=None)
    parser.add_argument("--language-model-name", default=None)
    parser.add_argument("--language-timeout-seconds", type=float, default=None)
    parser.add_argument("--language-max-retries", type=int, default=None)

    parser.add_argument("--max-longest-edge-px", type=int, default=None)
    parser.add_argument("--token-threshold", type=int, default=None)

    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser


def main() -> int:
    parser = build_parser()
    try:
        args = parser.parse_args()
        simple_args = SimpleNamespace(**vars(args))
        config = build_config_from_args(simple_args)
    except ConfigValidationError as exc:
        print(f"ERROR code={exc.error_code} message={exc}")
        return 2
    except Exception as exc:
        print(f"ERROR code=cli_argument_error message={type(exc).__name__}: {exc}")
        return 2

    if args.verbose:
        print(format_config_dump(config))

    return run_foundation_bootstrap(config)


if __name__ == "__main__":
    raise SystemExit(main())
