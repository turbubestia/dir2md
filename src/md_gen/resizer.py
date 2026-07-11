from __future__ import annotations

from dataclasses import dataclass
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


def _target_dimensions(width: int, height: int, max_longest_edge_px: int) -> tuple[int, int]:
    if max(width, height) <= max_longest_edge_px:
        return width, height
    if width >= height:
        return max_longest_edge_px, max(1, int(height * max_longest_edge_px / width))
    return max(1, int(width * max_longest_edge_px / height)), max_longest_edge_px


def resize_image_for_ocr(
    source_image_path: Path,
    output_dir: Path,
    max_longest_edge_px: int,
) -> ImageResizeResult:
    
    output_dir.mkdir(parents=True, exist_ok=True)

    # this will replace the original image if the source and output directories 
    # are the same, otherwise it will create a new file in the output directory
    source_image_path = source_image_path.resolve()
    if source_image_path.parent == output_dir.resolve():
        output_image_path = source_image_path
    else:
        output_image_path = output_dir / source_image_path.name

    # lets write the image to a temporary file first, then replace the original file with the temporary file
    temp_output_image_path = output_image_path.with_name(
        output_image_path.stem + ".tmp" + output_image_path.suffix
    )
    with Image.open(source_image_path) as image_handle:
        image = ImageOps.exif_transpose(image_handle)

        original_width, original_height = image.size
        resized_width, resized_height = _target_dimensions(
            original_width,
            original_height,
            max_longest_edge_px = max_longest_edge_px,
        )

        was_resized = (resized_width, resized_height) != (original_width, original_height)

        if output_image_path == source_image_path and not was_resized:
            pass
        elif was_resized:
            resized_image = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
            resized_image.save(temp_output_image_path)
            resized_image.close()
            temp_output_image_path.replace(output_image_path)
        else:
            copy2(source_image_path, output_image_path)
            
    return ImageResizeResult(
        source_image_path=source_image_path,
        output_image_path=output_image_path,
        original_width=original_width,
        original_height=original_height,
        resized_width=resized_width,
        resized_height=resized_height,
        was_resized=was_resized,
        max_longest_edge_px=max_longest_edge_px
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