from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.gateway import GatewayError, LlamaLanguageGateway, TextRequest, TextResponse
from common.config import AppConfig


def _dump_raw_response_json(config: AppConfig, raw_response: dict[str, Any]) -> None:
    output_dir = config.paths.output_dir
    if output_dir == Path():
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

def run_chat(config: AppConfig, system: Path, user: Path) -> int:
    # read system prompt file
    try:
        with system.open("r", encoding="utf-8") as f:
            system_prompt = f.read()
    except Exception as exc:
        print(f"ERROR reading system prompt file: {exc}")
        return 1

    # read user prompt file
    try:
        with user.open("r", encoding="utf-8") as f:
            user_prompt = f.read()
    except Exception as exc:
        print(f"ERROR reading user prompt file: {exc}")
        return 1
    
    print("Running chat...")

    request = TextRequest(system_prompt=system_prompt, user_prompt=user_prompt)
    gateway = LlamaLanguageGateway(
        endpoint_url=config.language_model.endpoint_url,
        model_name=config.language_model.model_name,
    )
    gateway.temperature = config.language_model.temperature
    
    try:
        response: TextResponse = gateway.send_text_request(request)
        print("Chat response:")
        print(response.text)
        _dump_raw_response_json(config, response.raw_response)
    except GatewayError as exc:
        print(f"ERROR sending chat request: {exc}")
        return 1

    return 0