from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .resizer import ImageResizeResult

TokenBudgetStatus = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class ImageTokenBudgetReport:
    image_path: str
    width: int
    height: int
    estimated_tokens: int
    token_threshold: int
    warning_threshold_tokens: int
    status: TokenBudgetStatus
    message: str


class TokenBudgetValidationError(RuntimeError):
    def __init__(self, reports: tuple[ImageTokenBudgetReport, ...]):
        self.reports = reports
        message = "; ".join(
            f"{report.image_path}={report.estimated_tokens}>{report.token_threshold}"
            for report in reports
            if report.status == "error"
        )
        super().__init__(f"One or more images exceeded token threshold: {message}")


def calculate_vision_tokens(width: int, height: int) -> int:
    return int((width * height) / 1024)


def evaluate_image_token_budget(
    image_resize_result: ImageResizeResult,
    token_threshold: int,
    warning_ratio: float = 0.9,
) -> ImageTokenBudgetReport:
    estimated_tokens = calculate_vision_tokens(
        width=image_resize_result.resized_width,
        height=image_resize_result.resized_height,
    )
    warning_threshold_tokens = int(token_threshold * warning_ratio)

    if estimated_tokens > token_threshold:
        status: TokenBudgetStatus = "error"
        message = (
            f"Image exceeds token threshold: {estimated_tokens} > {token_threshold}. "
            "Lower image dimensions before OCR submission."
        )
    elif estimated_tokens >= warning_threshold_tokens:
        status = "warning"
        message = (
            f"Image is near token threshold: {estimated_tokens} / {token_threshold}. "
            "OCR request may be fragile on larger prompts."
        )
    else:
        status = "ok"
        message = f"Image token budget is within threshold: {estimated_tokens} / {token_threshold}."

    return ImageTokenBudgetReport(
        image_path=image_resize_result.output_image_path.as_posix(),
        width=image_resize_result.resized_width,
        height=image_resize_result.resized_height,
        estimated_tokens=estimated_tokens,
        token_threshold=token_threshold,
        warning_threshold_tokens=warning_threshold_tokens,
        status=status,
        message=message,
    )


def evaluate_token_budget_for_images(
    resized_images: tuple[ImageResizeResult, ...],
    token_threshold: int,
    warning_ratio: float = 0.9,
) -> tuple[ImageTokenBudgetReport, ...]:
    return tuple(
        evaluate_image_token_budget(
            image_resize_result=image_result,
            token_threshold=token_threshold,
            warning_ratio=warning_ratio,
        )
        for image_result in resized_images
    )


def enforce_token_budget(reports: tuple[ImageTokenBudgetReport, ...]) -> None:
    failures = tuple(report for report in reports if report.status == "error")
    if failures:
        raise TokenBudgetValidationError(failures)