from pathlib import Path

from PIL import Image
from PIL import UnidentifiedImageError
import pytest

from md_gen.resizer import resize_image_for_ocr, resize_images_for_ocr


def _make_image(path: Path, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, color=(220, 220, 220))
    image.save(path)
    image.close()


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


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
    assert result.output_image_path.exists()
    assert _image_size(result.output_image_path) == (1540, 385)


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
    assert result.output_image_path.exists()
    assert _image_size(result.output_image_path) == (1000, 500)


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
    assert _image_size(source) == (900, 900)


def test_resize_equal_threshold_does_not_resize(tmp_path: Path) -> None:
    source = tmp_path / "edge_equal.png"
    _make_image(source, (1540, 1000))

    result = resize_image_for_ocr(
        source_image_path=source,
        output_dir=tmp_path / "im-temp",
        max_longest_edge_px=1540,
    )

    assert result.was_resized is False
    assert (result.resized_width, result.resized_height) == (1540, 1000)
    assert _image_size(result.output_image_path) == (1540, 1000)


def test_resize_portrait_image_preserves_aspect_ratio(tmp_path: Path) -> None:
    source = tmp_path / "portrait.jpg"
    _make_image(source, (1000, 4000))

    result = resize_image_for_ocr(
        source_image_path=source,
        output_dir=tmp_path / "im-temp",
        max_longest_edge_px=1540,
    )

    assert result.was_resized is True
    assert (result.resized_width, result.resized_height) == (385, 1540)
    assert _image_size(result.output_image_path) == (385, 1540)


def test_resize_in_place_replaces_output_image_when_resize_needed(tmp_path: Path) -> None:
    output_dir = tmp_path / "im-temp"
    output_dir.mkdir()
    source = output_dir / "page-001.jpg"
    _make_image(source, (3200, 1600))

    result = resize_image_for_ocr(
        source_image_path=source,
        output_dir=output_dir,
        max_longest_edge_px=1540,
    )

    assert result.output_image_path == source
    assert result.was_resized is True
    assert _image_size(source) == (1540, 770)


def test_resize_copies_non_output_source_when_no_resize_needed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output_dir = tmp_path / "im-temp"
    image_path = source / "original.png"
    _make_image(image_path, (900, 700))

    result = resize_image_for_ocr(
        source_image_path=image_path,
        output_dir=output_dir,
        max_longest_edge_px=1540,
    )

    assert result.was_resized is False
    assert result.output_image_path == output_dir / "original.png"
    assert result.output_image_path.exists()
    assert _image_size(image_path) == (900, 700)
    assert _image_size(result.output_image_path) == (900, 700)


def test_resize_does_not_modify_non_output_source_when_resized(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output_dir = tmp_path / "im-temp"
    image_path = source / "scan.jpg"
    _make_image(image_path, (4000, 1000))

    result = resize_image_for_ocr(
        source_image_path=image_path,
        output_dir=output_dir,
        max_longest_edge_px=1540,
    )

    assert result.was_resized is True
    assert _image_size(image_path) == (4000, 1000)
    assert _image_size(result.output_image_path) == (1540, 385)


def test_resize_images_for_ocr_mixed_batch_preserves_order(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "im-temp"

    large = source_dir / "large.jpg"
    small = source_dir / "small.png"
    _make_image(large, (4000, 1000))
    _make_image(small, (1000, 500))

    results = resize_images_for_ocr(
        source_image_paths=(large, small),
        output_dir=output_dir,
        max_longest_edge_px=1540,
    )

    assert len(results) == 2
    assert results[0].source_image_path == large.resolve()
    assert results[1].source_image_path == small.resolve()
    assert results[0].was_resized is True
    assert results[1].was_resized is False
    assert _image_size(results[0].output_image_path) == (1540, 385)
    assert _image_size(results[1].output_image_path) == (1000, 500)


def test_resize_images_for_ocr_empty_input_returns_empty_tuple(tmp_path: Path) -> None:
    output_dir = tmp_path / "im-temp"

    results = resize_images_for_ocr(
        source_image_paths=(),
        output_dir=output_dir,
        max_longest_edge_px=1540,
    )

    assert results == ()


def test_resize_image_for_ocr_raises_for_unreadable_image(tmp_path: Path) -> None:
    source = tmp_path / "broken.jpg"
    source.write_bytes(b"this is not a real image")

    with pytest.raises(UnidentifiedImageError):
        resize_image_for_ocr(
            source_image_path=source,
            output_dir=tmp_path / "im-temp",
            max_longest_edge_px=1540,
        )


def test_resize_images_for_ocr_raises_for_unreadable_image(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    good = source_dir / "good.png"
    bad = source_dir / "bad.png"
    _make_image(good, (900, 700))
    bad.write_bytes(b"not an image")

    with pytest.raises(UnidentifiedImageError):
        resize_images_for_ocr(
            source_image_paths=(good, bad),
            output_dir=tmp_path / "im-temp",
            max_longest_edge_px=1540,
        )
