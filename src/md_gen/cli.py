from __future__ import annotations

import argparse

from .config import ConfigValidationError, build_config_from_args
from .foundation import run_foundation_bootstrap

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-gen",
        description="Foundation CLI for markdown generation pipeline setup.",
    )

    parser.add_argument("--source", required=True, help="Source directory containing top-level input files.")
    parser.add_argument("--output", required=True, help="Output directory root for generated artifacts.")
    parser.add_argument(
        "--summary-prompt",
        default=None,
        help="Optional path to a summary system prompt file.",
    )

    parser.add_argument("--ocr-model-endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--ocr-model-name", default="lightonocr-2")
    parser.add_argument("--ocr-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--ocr-max-retries", type=int, default=2)

    parser.add_argument("--language-model-endpoint", default="http://localhost:8081/v1/chat/completions")
    parser.add_argument("--language-model-name", default="qwen3-1.7b")
    parser.add_argument("--language-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--language-max-retries", type=int, default=2)
    
    parser.add_argument("--max-longest-edge-px", type=int, default=1540)
    parser.add_argument("--token-threshold", type=int, default=16000)

    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--overwrite", action="store_true", default=False)
    return parser


def main() -> int:
    parser = build_parser()
    try:
        args = parser.parse_args()
        config = build_config_from_args(args)
    except ConfigValidationError as exc:
        print(f"ERROR code={exc.error_code} message={exc}")
        return 2
    except Exception as exc:
        print(f"ERROR code=cli_argument_error message={type(exc).__name__}: {exc}")
        return 2

    return run_foundation_bootstrap(config)


if __name__ == "__main__":
    raise SystemExit(main())
