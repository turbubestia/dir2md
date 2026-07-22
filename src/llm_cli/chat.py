from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.gateway import GatewayError, LlamaLanguageGateway, TextRequest, TextResponse
from common.config import AppConfig


def _validate_chat_inputs(config: AppConfig) -> None:
    if config.language_model.endpoint_url is None:
        raise ValueError("Language model endpoint must be configured before chat starts")
    if config.language_model.model_name is None:
        raise ValueError("Language model name must be configured before chat starts")


def _dump_raw_response_json(config: AppConfig, raw_response: dict[str, Any]) -> None:
    output_dir = config.paths.output_dir
    if output_dir is None or output_dir == Path():
        print("WARNING raw response not persisted: output directory is not configured")
        return

    output_path = output_dir / "raw_response.json"

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(raw_response, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except (OSError, TypeError, ValueError) as exc:
        print(f"WARNING failed to persist raw response JSON: {exc}")
        return

    print(f"Raw response saved to: {output_path}")


def _read_prompt_file(path: Path, label: str) -> str:
    try:
        with path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        raise ValueError(f"ERROR reading {label} prompt file: {exc}") from exc


def _send_chat_request(config: AppConfig, system_prompt: str, user_prompt: str, assistant_prompt: str) -> TextResponse:
    _validate_chat_inputs(config)

    request = TextRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        assistant_prompt=assistant_prompt,
    )

    gateway = LlamaLanguageGateway(
        endpoint_url=config.language_model.endpoint_url,
        model_name=config.language_model.model_name,
    )
    gateway.temperature = config.language_model.temperature
    gateway.top_p = config.language_model.top_p
    gateway.top_k = config.language_model.top_k
    gateway.min_p = config.language_model.min_p

    return gateway.send_text_request(request)


def run_chat_return_text(config: AppConfig, system: Path, user: Path, assistant: Path | None = None) -> str:
    system_prompt = _read_prompt_file(system, "system")
    user_prompt = _read_prompt_file(user, "user")
    assistant_prompt = _read_prompt_file(assistant, "assistant") if assistant is not None else ""

    response = _send_chat_request(config, system_prompt, user_prompt, assistant_prompt)
    _dump_raw_response_json(config, response.raw_response)
    return response.text


def run_chat(config: AppConfig, system: Path, user: Path, assistant: Path | None = None) -> int:
    try:
        response_text = run_chat_return_text(config, system, user, assistant)
    except ValueError as exc:
        print(str(exc))
        return 1
    except GatewayError as exc:
        print(f"ERROR sending chat request: {exc}")
        return 1

    print("Running chat...")
    print("Chat response:")
    print(response_text)
    return 0