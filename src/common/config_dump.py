from __future__ import annotations

from .config import AppConfig, LlamaModelSettings


def _append_model(lines: list[str], section: str, model: LlamaModelSettings) -> None:
    lines.extend(
        [
            f"[{section}]",
            f"endpoint_url={model.endpoint_url}",
            f"model_name={model.model_name}",
            f"request_timeout_seconds={model.request_timeout_seconds}",
            f"request_max_retries={model.request_max_retries}",
            f"temperature={model.temperature}",
            f"top_p={model.top_p}",
            f"top_k={model.top_k}",
            f"min_p={model.min_p}",
            "",
        ]
    )


def format_config_dump(config: AppConfig) -> str:

    lines = [
        "=== startup config dump ===",
        "[paths]",
        f"source_dir={config.paths.source_dir}",
        f"output_dir={config.paths.output_dir}",
        "",
        "[md_gen.prompts]",
        f"summary_prompt_path={config.md_gen.prompts.summary_prompt_path}",
        "summary_prompt_text:",
        config.md_gen.prompts.summary_prompt_text,
        "",
    ]
    _append_model(lines, "ocr_model", config.ocr_model)
    _append_model(lines, "language_model", config.language_model)
    lines.extend(
        [
            "[md_gen.image]",
            f"max_longest_edge_px={config.md_gen.image.max_longest_edge_px}",
            f"token_threshold={config.md_gen.image.token_threshold}",
            "",
            "[runtime]",
            f"dry_run={config.runtime.dry_run}",
            f"overwrite={config.runtime.overwrite}",
            f"verbose={config.runtime.verbose}",
            "=== end startup config dump ===",
        ]
    )
    return "\n".join(lines)