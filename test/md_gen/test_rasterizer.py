from pathlib import Path

import pytest
from PIL import Image

import md_gen.rasterizer as rasterizer
from md_gen.rasterizer import RasterizationError, get_pdf_page_count, rasterize_page, resize_image


def _make_test_pdf(pdf_path: Path, page_sizes: tuple[tuple[int, int], ...] = ((300, 120), (200, 200))) -> None:
    images = [Image.new("RGB", size, color=(255, 255, 255)) for size in page_sizes]
    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)
    for image in images:
        image.close()


def _make_test_image(image_path: Path, size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, color=(128, 128, 128))
    image.save(image_path)
    image.close()


class _FakePdfiumError(Exception):
    pass


class _FakeImage:
    def __init__(self, size: tuple[int, int]):
        self.size = size

    def close(self) -> None:
        return None


class _FakeBitmap:
    def __init__(self, image: _FakeImage):
        self._image = image

    def to_pil(self) -> _FakeImage:
        return self._image


class _FakePage:
    def __init__(
        self,
        size: tuple[int, int] = (123, 77),
        render_error: Exception | None = None,
        close_log: list[str] | None = None,
        page_name: str = "page",
    ):
        self._size = size
        self._render_error = render_error
        self._close_log = close_log if close_log is not None else []
        self._page_name = page_name

    def render(self, scale: float) -> _FakeBitmap:
        if self._render_error is not None:
            raise self._render_error
        return _FakeBitmap(_FakeImage(self._size))

    def close(self) -> None:
        self._close_log.append(f"{self._page_name}.close")


class _FakeDocument:
    def __init__(self, pages: tuple[_FakePage, ...], close_log: list[str]):
        self._pages = pages
        self._close_log = close_log

    def __len__(self) -> int:
        return len(self._pages)

    def get_page(self, page_index: int) -> _FakePage:
        return self._pages[page_index]

    def close(self) -> None:
        self._close_log.append("document.close")


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("Incorrect password", "encrypted_pdf"),
        ("This file is encrypted", "encrypted_pdf"),
        ("Data format error in stream", "corrupted_pdf"),
        ("PDF syntax error", "corrupted_pdf"),
        ("some other open problem", "unreadable_pdf"),
    ),
)
def test_classify_pdfium_error_branches(message: str, expected: str) -> None:
    assert rasterizer._classify_pdfium_error(message) == expected


def test_resize_image_downscales_longest_edge_and_preserves_aspect_ratio() -> None:
    image = Image.new("RGB", (4000, 1000), color=(220, 220, 220))
    resized = resize_image(image, 1540)

    assert resized.size == (1540, 385)
    image.close()
    resized.close()


def test_resize_image_keeps_small_image_dimensions_unchanged() -> None:
    image = Image.new("RGB", (1000, 500), color=(220, 220, 220))
    resized = resize_image(image, 1540)

    assert resized.size == (1000, 500)
    image.close()
    resized.close()


def test_rasterize_page_returns_resized_pdf_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_test_pdf(pdf_path, page_sizes=((300, 120), (200, 200)))

    image = rasterize_page(pdf_path, max_edge_size=1540, page_number=1)

    assert isinstance(image, Image.Image)
    assert image.size == (300, 120)
    image.close()


def test_rasterize_page_returns_resized_image(tmp_path: Path) -> None:
    image_path = tmp_path / "scan.png"
    _make_test_image(image_path, (4000, 1000))

    image = rasterize_page(image_path, max_edge_size=1540)

    assert isinstance(image, Image.Image)
    assert image.size == (1540, 385)
    image.close()


def test_rasterize_page_rejects_unsupported_file(tmp_path: Path) -> None:
    txt_path = tmp_path / "notes.txt"
    txt_path.write_text("not an image", encoding="utf-8")

    with pytest.raises(RasterizationError) as exc_info:
        rasterize_page(txt_path, max_edge_size=1540)

    assert exc_info.value.error_code == "unsupported_file"
    assert exc_info.value.source_path == txt_path


def test_rasterize_page_rejects_missing_input(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing.pdf"

    with pytest.raises(RasterizationError) as exc_info:
        rasterize_page(missing_pdf, max_edge_size=1540)

    assert exc_info.value.error_code == "missing_input"
    assert exc_info.value.source_path == missing_pdf


@pytest.mark.parametrize(
    ("message", "expected_code"),
    (
        ("Incorrect password", "encrypted_pdf"),
        ("Data format problem", "corrupted_pdf"),
        ("unknown open failure", "unreadable_pdf"),
    ),
)
def test_rasterize_page_pdf_open_failure_error_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    expected_code: str,
) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((100, 100),))

    def _raise_on_open(_path: Path) -> None:
        raise _FakePdfiumError(message)

    monkeypatch.setattr(rasterizer.pdfium, "PdfiumError", _FakePdfiumError)
    monkeypatch.setattr(rasterizer.pdfium, "PdfDocument", _raise_on_open)

    with pytest.raises(RasterizationError) as exc_info:
        rasterize_page(pdf_path, max_edge_size=1540)

    assert exc_info.value.error_code == expected_code
    assert exc_info.value.source_path == pdf_path


def test_rasterize_page_render_failure_closes_page_and_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((100, 100),))

    close_log: list[str] = []
    page = _FakePage(
        render_error=_FakePdfiumError("syntax error while rendering"),
        close_log=close_log,
        page_name="page-0",
    )
    fake_document = _FakeDocument(pages=(page,), close_log=close_log)

    monkeypatch.setattr(rasterizer.pdfium, "PdfiumError", _FakePdfiumError)
    monkeypatch.setattr(rasterizer.pdfium, "PdfDocument", lambda _path: fake_document)

    with pytest.raises(RasterizationError) as exc_info:
        rasterize_page(pdf_path, max_edge_size=1540)

    assert exc_info.value.error_code == "corrupted_pdf"
    assert close_log == ["page-0.close", "document.close"]


def test_rasterize_page_rejects_invalid_page_number(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((100, 100),))

    close_log: list[str] = []
    fake_document = _FakeDocument(pages=(), close_log=close_log)
    monkeypatch.setattr(rasterizer.pdfium, "PdfDocument", lambda _path: fake_document)

    with pytest.raises(RasterizationError) as exc_info:
        rasterize_page(pdf_path, max_edge_size=1540, page_number=1)

    assert exc_info.value.error_code == "unreadable_pdf"
    assert close_log == ["document.close"]


def test_get_pdf_page_count_returns_total_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((100, 100), (200, 200), (300, 300)))

    assert get_pdf_page_count(pdf_path) == 3


def test_get_pdf_page_count_rejects_missing_input(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing.pdf"

    with pytest.raises(RasterizationError) as exc_info:
        get_pdf_page_count(missing_pdf)

    assert exc_info.value.error_code == "missing_input"


def test_get_pdf_page_count_rejects_non_pdf(tmp_path: Path) -> None:
    image_path = tmp_path / "scan.png"
    _make_test_image(image_path, (100, 100))

    with pytest.raises(RasterizationError) as exc_info:
        get_pdf_page_count(image_path)

    assert exc_info.value.error_code == "unsupported_file"