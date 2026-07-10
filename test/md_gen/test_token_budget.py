from pathlib import Path

from md_gen.resizer import ImageResizeResult
from md_gen.token_budget import (
    TokenBudgetValidationError,
    calculate_vision_tokens,
    enforce_token_budget,
    evaluate_image_token_budget,
    evaluate_token_budget_for_images,
)


def _resize_result(path: Path, width: int, height: int) -> ImageResizeResult:
    return ImageResizeResult(
        source_image_path=path,
        output_image_path=path,
        original_width=width,
        original_height=height,
        resized_width=width,
        resized_height=height,
        was_resized=False,
        max_longest_edge_px=1540,
        is_valid_for_ocr=True,
    )


def test_calculate_vision_tokens_uses_lighton_formula() -> None:
    assert calculate_vision_tokens(width=1540, height=1540) == int((1540 * 1540) / 1024)
    assert calculate_vision_tokens(width=1024, height=1024) == 1024


def test_evaluate_image_token_budget_returns_warning_near_threshold(tmp_path: Path) -> None:
    image_result = _resize_result(tmp_path / "near.png", 1360, 1360)

    report = evaluate_image_token_budget(
        image_resize_result=image_result,
        token_threshold=2000,
    )

    assert report.estimated_tokens == int((1360 * 1360) / 1024)
    assert report.status == "warning"


def test_evaluate_image_token_budget_returns_error_above_threshold(tmp_path: Path) -> None:
    image_result = _resize_result(tmp_path / "over.png", 1540, 1540)

    report = evaluate_image_token_budget(
        image_resize_result=image_result,
        token_threshold=2000,
    )

    assert report.estimated_tokens == int((1540 * 1540) / 1024)
    assert report.status == "error"


def test_enforce_token_budget_raises_for_error_reports(tmp_path: Path) -> None:
    ok_result = _resize_result(tmp_path / "ok.png", 1000, 1000)
    bad_result = _resize_result(tmp_path / "bad.png", 1540, 1540)

    reports = evaluate_token_budget_for_images(
        resized_images=(ok_result, bad_result),
        token_threshold=2000,
    )

    try:
        enforce_token_budget(reports)
    except TokenBudgetValidationError as exc:
        assert len(exc.reports) == 1
        assert exc.reports[0].status == "error"
    else:
        raise AssertionError("Expected TokenBudgetValidationError")
