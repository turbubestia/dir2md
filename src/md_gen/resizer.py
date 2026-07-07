from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from shutil import copy2

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ImageResizeResult:
    source_image_path: Path
    output_image_path: Path
    original_width: int
    original_height: int
    resized_width: int
    resized_height: int
    was_resized: bool
    max_longest_edge_px: int
    is_valid_for_ocr: bool


def _sanitize_stem(path: Path) -> str:
    cleaned = []
    for char in path.stem.lower():
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "image"


def _deterministic_output_name(source_image_path: Path) -> str:
    source_hash = sha1(source_image_path.as_posix().encode("utf-8")).hexdigest()[:10]
    suffix = source_image_path.suffix.lower() or ".img"
    return f"{_sanitize_stem(source_image_path)}-{source_hash}{suffix}"


def _target_dimensions(width: int, height: int, max_longest_edge_px: int) -> tuple[int, int]:
    if max(width, height) <= max_longest_edge_px:
        return width, height
    if width >= height:
        return max_longest_edge_px, max(1, int(height * max_longest_edge_px / width))
    return max(1, int(width * max_longest_edge_px / height)), max_longest_edge_px


def _is_valid_dimensions(width: int, height: int, max_longest_edge_px: int) -> bool:
    return width > 0 and height > 0 and max(width, height) <= max_longest_edge_px


def resize_image_for_ocr(
    source_image_path: Path,
    output_dir: Path,
    max_longest_edge_px: int,
) -> ImageResizeResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_image_path = source_image_path.resolve()

    if source_image_path.parent == output_dir.resolve():
        output_image_path = source_image_path
    else:
        output_image_path = output_dir / _deterministic_output_name(source_image_path)

    with Image.open(source_image_path) as image_handle:
        image = ImageOps.exif_transpose(image_handle)
        original_width, original_height = image.size
        resized_width, resized_height = _target_dimensions(
            original_width,
            original_height,
            max_longest_edge_px=max_longest_edge_px,
        )
        was_resized = (resized_width, resized_height) != (original_width, original_height)

        if was_resized:
            resized_image = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            save_image = resized_image
        else:
            save_image = image

        if output_image_path == source_image_path and not was_resized:
            pass
        elif not was_resized:
            copy2(source_image_path, output_image_path)
        else:
            save_image.save(output_image_path)

        if was_resized:
            save_image.close()

    is_valid_for_ocr = _is_valid_dimensions(resized_width, resized_height, max_longest_edge_px)
    return ImageResizeResult(
        source_image_path=source_image_path,
        output_image_path=output_image_path,
        original_width=original_width,
        original_height=original_height,
        resized_width=resized_width,
        resized_height=resized_height,
        was_resized=was_resized,
        max_longest_edge_px=max_longest_edge_px,
        is_valid_for_ocr=is_valid_for_ocr,
    )


def resize_images_for_ocr(
    source_image_paths: tuple[Path, ...],
    output_dir: Path,
    max_longest_edge_px: int,
) -> tuple[ImageResizeResult, ...]:
    return tuple(
        resize_image_for_ocr(
            source_image_path=source_image_path,
            output_dir=output_dir,
            max_longest_edge_px=max_longest_edge_px,
        )
        for source_image_path in source_image_paths
    )