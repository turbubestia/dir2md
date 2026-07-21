from __future__ import annotations

import argparse
from pathlib import Path

from common.config import ConfigValidationError, build_config_from_overrides
from common.config_dump import format_config_dump

from .chat import run_chat

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-cli",
        description="LLM cli to test the language model."
    )
    # Add your arguments here
    parser.add_argument("-s", "--system", required=True, help="Specify the system prompt file for the LLM.")
    parser.add_argument("-u", "--user", required=True, help="Specify the user prompt file for the LLM.")
    parser.add_argument("-a", "--assistant", help="Specify the assistant prompt file for the LLM.", default=None)
    parser.add_argument("-o", "--output", help="Specify the output file for the LLM raw response.", default=None)

    parser.add_argument("-t", "--temperature", type=float, help="Specify the temperature for the LLM response.", default=None)
    parser.add_argument("--top-p", type=float, help="Specify the top-p value for the LLM response.", default=None)
    parser.add_argument("--top-k", type=int, help="Specify the top-k value for the LLM response.", default=None)
    parser.add_argument("--min-p", type=float, help="Specify the minimum probability for the LLM response.", default=None)

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output for the LLM CLI.")

    return parser


def build_config_overrides(args: argparse.Namespace) -> dict[str, object]:
    language_model = {
        key: value
        for key, value in {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "top_k": args.top_k,
            "min_p": args.min_p,
        }.items()
        if value is not None
    }

    overrides: dict[str, object] = {}
    if language_model:
        overrides["language_model"] = language_model
    if args.verbose:
        overrides["runtime"] = {"verbose": True}

    if args.output is not None:
        overrides["paths"] = {"output_dir": str(Path(args.output).expanduser().resolve())}

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

    system_prompt = Path(args.system).expanduser().resolve()
    user_prompt = Path(args.user).expanduser().resolve()
    assistant_prompt = Path(args.assistant).expanduser().resolve() if args.assistant is not None else None

    if config.runtime.verbose:
        print(format_config_dump(config))
        print(
            "\n[Prompts]\n",
            f"system_prompt={system_prompt}\n",
            f"user_prompt={user_prompt}\n",
            f"assistant_prompt={assistant_prompt}\n" if assistant_prompt is not None else "",
        )

    return run_chat(config, system_prompt, user_prompt, assistant_prompt)

if __name__ == "__main__":
    raise SystemExit(main())