from __future__ import annotations

import argparse
from pathlib import Path

from .apply import apply_merge_plan
from .models import PlanConfig
from .planner import build_merge_plan


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-mrg",
        description="Merge planning and execution for OCR markdown fragments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Build merge plan from md-temp metadata JSON files")
    plan.add_argument("--md-temp-dir", required=True)
    plan.add_argument("--mg-temp-dir", required=True)
    plan.add_argument("--edge-scorer", choices=("heuristic", "llm"), default="heuristic")
    plan.add_argument("--rolling-window", type=int, default=5)
    plan.add_argument("--llm-endpoint-url", default="http://localhost:8081/v1/chat/completions")
    plan.add_argument("--llm-model-name", default="qwen3-1.7b")
    plan.add_argument("--llm-timeout-seconds", type=float, default=120.0)
    plan.add_argument("--llm-max-retries", type=int, default=2)
    plan.add_argument("--overwrite", action="store_true", default=False)

    apply = subparsers.add_parser("apply", help="Apply merge plan artifact and write merged markdown")
    apply.add_argument("--merge-batch-file", required=True)
    apply.add_argument("--output-dir", required=True)
    apply.add_argument("--md-temp-dir", default=None)
    apply.add_argument("--im-temp-dir", default=None)
    apply.add_argument("--naming-endpoint-url", default="http://localhost:8081/v1/chat/completions")
    apply.add_argument("--naming-model-name", default="qwen3-1.7b")
    apply.add_argument("--naming-timeout-seconds", type=float, default=30.0)
    apply.add_argument("--naming-max-retries", type=int, default=0)
    apply.add_argument("--overwrite", action="store_true", default=False)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "plan":
        config = PlanConfig(
            md_temp_dir=Path(args.md_temp_dir).expanduser().resolve(),
            mg_temp_dir=Path(args.mg_temp_dir).expanduser().resolve(),
            edge_scorer=args.edge_scorer,
            rolling_window=max(1, int(args.rolling_window)),
            llm_endpoint_url=args.llm_endpoint_url,
            llm_model_name=args.llm_model_name,
            llm_timeout_seconds=float(args.llm_timeout_seconds),
            llm_max_retries=max(0, int(args.llm_max_retries)),
            overwrite=args.overwrite,
        )
        result = build_merge_plan(config)
        print(f"> wrote merge plan {result.output_path} (documents={result.document_count})")
        return 0

    return apply_merge_plan(
        merge_batch_file=Path(args.merge_batch_file).expanduser().resolve(),
        output_dir=Path(args.output_dir).expanduser().resolve(),
        md_temp_dir=Path(args.md_temp_dir).expanduser().resolve() if args.md_temp_dir else None,
        im_temp_dir=Path(args.im_temp_dir).expanduser().resolve() if args.im_temp_dir else None,
        naming_endpoint_url=args.naming_endpoint_url,
        naming_model_name=args.naming_model_name,
        naming_timeout_seconds=float(args.naming_timeout_seconds),
        naming_max_retries=max(0, int(args.naming_max_retries)),
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    raise SystemExit(main())
