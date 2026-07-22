from __future__ import annotations

import argparse

from common.config import ConfigValidationError, build_config_from_overrides
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


def build_config_overrides(args: argparse.Namespace) -> dict[str, object]:
    overrides: dict[str, object] = {"paths": {"source_dir": args.source, "output_dir": args.output}}

    ocr_model = {
        key: value
        for key, value in {
            "endpoint": args.ocr_model_endpoint,
            "model": args.ocr_model_name,
            "timeout_seconds": args.ocr_timeout_seconds,
            "max_retries": args.ocr_max_retries,
        }.items()
        if value is not None
    }
    if ocr_model:
        overrides["ocr_model"] = ocr_model

    language_model = {
        key: value
        for key, value in {
            "endpoint": args.language_model_endpoint,
            "model": args.language_model_name,
            "timeout_seconds": args.language_timeout_seconds,
            "max_retries": args.language_max_retries,
        }.items()
        if value is not None
    }
    if language_model:
        overrides["language_model"] = language_model

    md_gen: dict[str, object] = {}
    summary = {key: value for key, value in {"system_prompt": args.summary_prompt}.items() if value is not None}
    if summary:
        md_gen["summary"] = summary
    image = {
        key: value
        for key, value in {
            "max_longest_edge_px": args.max_longest_edge_px,
            "token_threshold": args.token_threshold,
        }.items()
        if value is not None
    }
    if image:
        md_gen["image"] = image
    if md_gen:
        overrides["md_gen"] = md_gen

    runtime = {key: True for key, enabled in {"dry_run": args.dry_run, "overwrite": args.overwrite, "verbose": args.verbose}.items() if enabled}
    if runtime:
        overrides["runtime"] = runtime

    return overrides

def main() -> int:
    parser = build_parser()
    try:
        args = parser.parse_args()
        config = build_config_from_overrides(build_config_overrides(args))
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
