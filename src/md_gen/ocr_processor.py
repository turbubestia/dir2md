from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from .config import AppConfig, ConfigValidationError
from .discovery import FileItem, build_work_items
from .resizer import ImageResizeResult

from common.gateway import GatewayError

from common.gateway import (
    OcrResponse,
    LlamaOcrGateway
)

from common.gateway import (
    TextResponse,
    TextRequest,
    LlamaLanguageGateway,
)

@dataclass(frozen=True)
class SummaryAttempt:
    image_path: Path
    summary_text: str
    failed: bool
    error_code: str | None


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

    ocr_requests = tuple(unique_image_paths)
    
    with LlamaOcrGateway(
        endpoint_url=config.ocr_model.endpoint_url,
        model_name=config.ocr_model.model_name,
    ) as gateway:
        responses: list[OcrResponse] = []
        for request in ocr_requests:
            print(f"> processing image {request}")
            responses.append(gateway.send_ocr_request(request))
        return tuple(responses)


def execute_summaries(
    config: AppConfig,
    ocr_responses: tuple[OcrResponse, ...],
) -> tuple[SummaryAttempt, ...]:
    
    attempts: list[SummaryAttempt] = []
    system_prompt = config.prompts.summary_prompt_text
    
    with LlamaLanguageGateway(
        endpoint_url=config.language_model.endpoint_url,
        model_name=config.language_model.model_name,
    ) as gateway:
        for response in ocr_responses:
            try:
                print(f"> processing summary for image {response.image_path}")
                summary_response = gateway.send_text_request(
                    TextRequest(system_prompt=system_prompt, user_prompt=response.markdown_text)
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
                        summary_text=summary_response.text,
                        failed=False,
                        error_code=None,
                    )
                )
    return tuple(attempts)