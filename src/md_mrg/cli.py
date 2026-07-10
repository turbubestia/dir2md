from __future__ import annotations

import argparse
from pathlib import Path

from .apply import ApplyError, apply_merge_plan
from .io import derive_image_dir, derive_markdown_dir, derive_metadata_dir, derive_plan_file, derive_temp_root
from .models import PlanConfig
from .planner import build_merge_plan


DEFAULT_SCORE_PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "md_mrg_bridge_score_system_prompt.txt"
BUILTIN_SCORE_PROMPT = (
    "You are an expert document reconstruction engineer. Review the end of Page A and the start of Page B "
    "along with their summaries. Rate how naturally, grammatically, or contextually Page B continues Page A "
    "on a scale from 0 to 10.\n\n"
    "Scoring Rules:\n"
    "10 = Perfect grammatical fit.\n"
    "7 = Paragraph split or figure/table insertion continuity.\n"
    "5 = Minimum continuity.\n"
    "4 = Similar content but likely different document.\n"
    "3 = Major topic pivot or disjointed vocabulary.\n"
    "0 = Totally unrelated pages.\n\n"
    "Output raw JSON matching this schema exactly: {\"reason\": \"string\", \"bridge_score\": integer}"
)


class MrgCliError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-mrg",
        description="Merge planning and execution for OCR markdown fragments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Build merge plan from source/temp metadata JSON files")
    plan.add_argument("--source", required=True)
    plan.add_argument("--edge-scorer", choices=("llm",), default="llm")
    plan.add_argument("--rolling-window", type=int, default=5)
    plan.add_argument("--llm-endpoint-url", default="http://localhost:8081/v1/chat/completions")
    plan.add_argument("--llm-model-name", default="qwen3-1.7b")
    plan.add_argument("--llm-timeout-seconds", type=float, default=120.0)
    plan.add_argument("--llm-max-retries", type=int, default=2)
    plan.add_argument("--score-prompt", default=None)
    plan.add_argument("--overwrite", action="store_true", default=False)

    apply = subparsers.add_parser("apply", help="Apply merge plan from source root and write merged artifacts")
    apply.add_argument("--source", required=True)
    apply.add_argument("--naming-endpoint-url", default="http://localhost:8081/v1/chat/completions")
    apply.add_argument("--naming-model-name", default="qwen3-1.7b")
    apply.add_argument("--naming-timeout-seconds", type=float, default=30.0)
    apply.add_argument("--naming-max-retries", type=int, default=0)
    apply.add_argument("--overwrite", action="store_true", default=False)

    return parser


def _resolve_source_root(raw_source: str) -> Path:
    source_root = Path(raw_source).expanduser().resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise MrgCliError("invalid_source_directory", f"--source must be an existing directory: {source_root}")
    return source_root


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        source_root = _resolve_source_root(args.source)

        if args.command == "plan":
            metadata_dir = derive_metadata_dir(source_root)
            print(f"PLAN source={source_root}")
            print(f"PLAN metadata_dir={metadata_dir}")
            print(f"PLAN plan_file={derive_plan_file(source_root)}")
            if not metadata_dir.exists() or not metadata_dir.is_dir():
                raise MrgCliError("metadata_temp_missing", f"Metadata temp directory not found: {metadata_dir}")

            config = PlanConfig(
                source_root=source_root,
                temp_root=derive_temp_root(source_root),
                metadata_dir=metadata_dir,
                markdown_dir=derive_markdown_dir(source_root),
                image_dir=derive_image_dir(source_root),
                plan_file=derive_plan_file(source_root),
                edge_scorer="llm",
                rolling_window=max(1, int(args.rolling_window)),
                llm_endpoint_url=args.llm_endpoint_url,
                llm_model_name=args.llm_model_name,
                llm_timeout_seconds=float(args.llm_timeout_seconds),
                llm_max_retries=max(0, int(args.llm_max_retries)),
                score_prompt_override_path=Path(args.score_prompt).expanduser().resolve() if args.score_prompt else None,
                score_prompt_default_path=DEFAULT_SCORE_PROMPT_FILE,
                score_prompt_builtin_text=BUILTIN_SCORE_PROMPT,
                overwrite=args.overwrite,
            )
            result = build_merge_plan(config)
            print(f"> wrote merge plan {result.output_path} (documents={result.document_count})")
            return 0

        return apply_merge_plan(
            source_root=source_root,
            naming_endpoint_url=args.naming_endpoint_url,
            naming_model_name=args.naming_model_name,
            naming_timeout_seconds=float(args.naming_timeout_seconds),
            naming_max_retries=max(0, int(args.naming_max_retries)),
            overwrite=args.overwrite,
        )
    except MrgCliError as exc:
        print(f"ERROR code={exc.error_code} message={exc}")
        return 2
    except ApplyError as exc:
        print(f"ERROR code={exc.error_code} message={exc}")
        return 3
    except Exception as exc:
        print(f"ERROR code=md_mrg_runtime_error message={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
