from pathlib import Path

from PIL import Image

from md_gen.resizer import resize_image_for_ocr


def _make_image(path: Path, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, color=(220, 220, 220))
    image.save(path)
    image.close()


def test_resize_downscales_longest_edge_and_preserves_aspect_ratio(tmp_path: Path) -> None:
    source = tmp_path / "large.jpg"
    _make_image(source, (4000, 1000))

    result = resize_image_for_ocr(
        source_image_path=source,
        output_dir=tmp_path / "im-temp",
        max_longest_edge_px=1540,
    )

    assert result.was_resized is True
    assert result.resized_width == 1540
    assert result.resized_height == 385
    assert result.is_valid_for_ocr is True
    assert result.output_image_path.exists()


def test_resize_keeps_small_image_dimensions_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "small.png"
    _make_image(source, (1000, 500))

    result = resize_image_for_ocr(
        source_image_path=source,
        output_dir=tmp_path / "im-temp",
        max_longest_edge_px=1540,
    )

    assert result.was_resized is False
    assert (result.original_width, result.original_height) == (1000, 500)
    assert (result.resized_width, result.resized_height) == (1000, 500)
    assert result.is_valid_for_ocr is True
    assert result.output_image_path.exists()


def test_resize_uses_in_place_path_for_images_already_in_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "im-temp"
    output_dir.mkdir()
    source = output_dir / "already-temp.png"
    _make_image(source, (900, 900))

    result = resize_image_for_ocr(
        source_image_path=source,
        output_dir=output_dir,
        max_longest_edge_px=1540,
    )

    assert result.output_image_path == source
    assert result.was_resized is False
    assert result.is_valid_for_ocr is True
