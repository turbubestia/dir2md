from __future__ import annotations

import argparse
from types import SimpleNamespace
from pathlib import Path

from common.config import ConfigValidationError, build_config_from_args
from common.config_dump import format_config_dump

from .chat import run_chat

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmcli",
        description="LLM cli to test the language model."
    )
    # Add your arguments here
    parser.add_argument("-s", "--system", required=True, help="Specify the system prompt file for the LLM.")
    parser.add_argument("-u", "--user", required=True, help="Specify the user prompt file for the LLM.")
    parser.add_argument("-o", "--output", help="Specify the output file for the LLM raw response.", default=None)

    parser.add_argument("-t", "--temperature", type=float, help="Specify the temperature for the LLM response.", default=None)
    parser.add_argument("--top-p", type=float, help="Specify the top-p value for the LLM response.", default=None)
    parser.add_argument("--top-k", type=int, help="Specify the top-k value for the LLM response.", default=None)
    parser.add_argument("--min-p", type=float, help="Specify the minimum probability for the LLM response.", default=None)

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output for the LLM CLI.")

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

    system_prompt = Path(args.system).expanduser().resolve()
    user_prompt = Path(args.user).expanduser().resolve()

    # override the language model settings if specified in the CLI arguments
    if args.temperature is not None:
        config.language_model.temperature = args.temperature
    if args.top_p is not None:
        config.language_model.top_p = args.top_p
    if args.top_k is not None:
        config.language_model.top_k = args.top_k
    if args.min_p is not None:
        config.language_model.min_p = args.min_p

    if config.runtime.verbose:
        print(format_config_dump(config))
        print(
            "\n[Prompts]\n",
            f"system_prompt={system_prompt}\n",
            f"user_prompt={user_prompt}\n",
        )

    return run_chat(config, system_prompt, user_prompt)

if __name__ == "__main__":
    raise SystemExit(main())