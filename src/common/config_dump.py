from __future__ import annotations

from .config import AppConfig


def _append_model(lines: list[str], section: str, model: object) -> None:
    lines.extend(
        [
            f"[{section}]",
            f"endpoint_url={model.endpoint_url}",
            f"model_name={model.model_name}",
            f"request_timeout_seconds={model.request_timeout_seconds}",
            f"request_max_retries={model.request_max_retries}",
            "",
        ]
    )


def format_config_dump(config: AppConfig, command: str = "md-gen") -> str:
    if command == "md-mrg":
        lines = [
            "=== md-mrg startup config dump ===",
            "[paths]",
            f"source_dir={config.paths.source_dir}",
            "",
        ]
        _append_model(lines, "language_model", config.language_model)
        lines.extend(
            [
                "[md_mrg]",
                f"score_prompt_path={config.md_mrg.score.summary_prompt_path}",
                "score_prompt_text:",
                config.md_mrg.score.summary_prompt_text,
                "",
                "[runtime]",
                f"dry_run={config.runtime.dry_run}",
                f"overwrite={config.runtime.overwrite}",
                "=== end startup config dump ===",
            ]
        )
        return "\n".join(lines)

    lines = [
        "=== md-gen startup config dump ===",
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
            "=== end startup config dump ===",
        ]
    )
    return "\n".join(lines)