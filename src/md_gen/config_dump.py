from __future__ import annotations

from .config import AppConfig


def format_config_dump(config: AppConfig) -> str:
    lines = [
        "=== md-gen startup config dump ===",
        "[paths]",
        f"source_dir={config.paths.source_dir}",
        f"output_dir={config.paths.output_dir}",
        f"temp_dir={config.paths.temp_dir}",
        "",
        "[prompts]",
        f"summary_prompt_path={config.prompts.summary_prompt_path}",
        "summary_prompt_text:",
        config.prompts.summary_prompt_text,
        "",
        "[ocr_model]",
        f"endpoint_url={config.ocr_model.endpoint_url}",
        f"model_name={config.ocr_model.model_name}",
        f"request_timeout_seconds={config.ocr_model.request_timeout_seconds}",
        f"request_max_retries={config.ocr_model.request_max_retries}",
        "",
        "[language_model]",
        f"endpoint_url={config.language_model.endpoint_url}",
        f"model_name={config.language_model.model_name}",
        f"request_timeout_seconds={config.language_model.request_timeout_seconds}",
        f"request_max_retries={config.language_model.request_max_retries}",
        "",
        "[image]",
        f"max_longest_edge_px={config.image.max_longest_edge_px}",
        f"token_threshold={config.image.token_threshold}",
        "",
        "[runtime]",
        f"dry_run={config.runtime.dry_run}",
        f"overwrite={config.runtime.overwrite}",
        "=== end startup config dump ===",
    ]
    return "\n".join(lines)