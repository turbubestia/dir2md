from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from .config import AppConfig, ConfigValidationError
from .discovery import WorkItem, build_work_items
from .resizer import ImageResizeResult

from common.gateway import (
    GatewayError,
    OcrResponse,
    LlamaOcrGateway,
    SummaryRequest,
    LlamaSummaryGateway,
    build_default_ocr_requests,
)

@dataclass(frozen=True)
class SummaryAttempt:
    image_path: Path
    summary_text: str
    failed: bool
    error_code: str | None

# def _load_prompt_file(path: Path) -> str | None:
#     try:
#         text = path.read_text(encoding="utf-8").strip()
#     except OSError:
#         return None
#     if not text:
#         return None
#     return text


# def load_summary_system_prompt(config: AppConfig) -> str:
#     override_path = config.prompts.summary_prompt_override_path
#     default_path = config.prompts.summary_prompt_default_path

#     if override_path is not None:
#         override_text = _load_prompt_file(override_path)
#         if override_text is not None:
#             print(f"PROMPT status=loaded source=override path={override_path}")
#             return override_text
#         print(f"PROMPT status=fallback source=override_unreadable path={override_path}")

#     default_text = _load_prompt_file(default_path)
#     if default_text is not None:
#         print(f"PROMPT status=loaded source=default path={default_path}")
#         return default_text

#     print("PROMPT status=fallback source=builtin")
#     return config.prompts.summary_prompt_builtin_text

def execute_ocr(
    config: AppConfig,
    resized_images: tuple[ImageResizeResult, ...],
) -> tuple[OcrResponse, ...]:
    
    unique_image_paths: list[Path] = []
    seen: set[Path] = set()

    for image in resized_images:
        resolved_path = image.output_image_path.resolve()
        if resolved_path in seen:
            continue
        seen.add(resolved_path)
        unique_image_paths.append(resolved_path)

    ocr_requests = build_default_ocr_requests(tuple(unique_image_paths))
    
    with LlamaOcrGateway(
        endpoint_url=config.ocr_model.endpoint_url,
        model_name=config.ocr_model.model_name,
        request_timeout_seconds=config.ocr_model.request_timeout_seconds,
        request_max_retries=config.ocr_model.request_max_retries,
    ) as gateway:
        responses: list[OcrResponse] = []
        for request in ocr_requests:
            print(f"> processing image {request.image_path}")
            responses.append(gateway.send_ocr_request(request))
        return tuple(responses)


def execute_summaries(
    config: AppConfig,
    ocr_responses: tuple[OcrResponse, ...],
) -> tuple[SummaryAttempt, ...]:
    
    attempts: list[SummaryAttempt] = []
    system_prompt = config.prompts.summary_prompt_text
    
    with LlamaSummaryGateway(
        endpoint_url=config.language_model.endpoint_url,
        model_name=config.language_model.model_name,
        request_timeout_seconds=config.language_model.request_timeout_seconds,
        request_max_retries=config.language_model.request_max_retries,
    ) as gateway:
        for response in ocr_responses:
            try:
                print(f"> processing summary for image {response.image_path}")
                summary_response = gateway.send_summary_request(
                    SummaryRequest(source_text=response.markdown_text, system_prompt=system_prompt)
                )
            except GatewayError as exc:
                attempts.append(
                    SummaryAttempt(
                        image_path=response.image_path.resolve(),
                        summary_text="",
                        failed=True,
                        error_code=exc.error_code,
                    )
                )
            except Exception:
                attempts.append(
                    SummaryAttempt(
                        image_path=response.image_path.resolve(),
                        summary_text="",
                        failed=True,
                        error_code="unknown_error",
                    )
                )
            else:
                attempts.append(
                    SummaryAttempt(
                        image_path=response.image_path.resolve(),
                        summary_text=summary_response.summary_text,
                        failed=False,
                        error_code=None,
                    )
                )
    return tuple(attempts)