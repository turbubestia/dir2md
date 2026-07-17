from __future__ import annotations

import argparse
from types import SimpleNamespace

from common.config import ConfigValidationError, build_md_mrg_config_from_args

from .apply import ApplyError, run_apply
from .planner import PlannerError, run_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-mrg",
        description="Plan and apply markdown merge workflow for loose scanned image pages.",
    )

    parser.add_argument("--source", required=True, help="Path to md_gen output directory containing batch.json.")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--plan", action="store_true", help="Build batch_mrg.json from batch.json.")
    mode_group.add_argument("--apply", action="store_true", help="Apply batch_mrg.json and generate merged artifacts.")

    parser.add_argument("--language-model-endpoint", default=None)
    parser.add_argument("--language-model-name", default=None)
    parser.add_argument("--language-timeout-seconds", type=float, default=None)
    parser.add_argument("--language-max-retries", type=int, default=None)

    return parser


def main() -> int:
    parser = build_parser()

    try:
        args = parser.parse_args()
        config = build_md_mrg_config_from_args(SimpleNamespace(**vars(args)))
    except ConfigValidationError as exc:
        print(f"ERROR code={exc.error_code} message={exc}")
        return 2
    except Exception as exc:
        print(f"ERROR code=cli_argument_error message={type(exc).__name__}: {exc}")
        return 2

    try:
        if args.plan:
            run_plan(source_dir=config.source_dir, cfg=config)
            return 0

        run_apply(source_dir=config.source_dir, cfg=config)
        return 0
    except (PlannerError, ApplyError) as exc:
        print(f"ERROR code={exc.error_code} message={exc}")
        return 1
    except Exception as exc:
        print(f"ERROR code=md_mrg_runtime_error message={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
