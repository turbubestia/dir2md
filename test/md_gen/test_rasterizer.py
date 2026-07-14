from pathlib import Path

import pytest
from PIL import Image

import md_gen.rasterizer as rasterizer
from md_gen.discovery import SourceType, FileItem
from md_gen.rasterizer import (
    PdfRasterizationError,
    _build_output_image_path,
    _classify_pdfium_error_message,
    rasterize_pdf_work_item,
    rasterize_pdf_work_items,
)


def _make_work_item(path: Path, source_type: SourceType = "pdf", order_index: int = 0, ordering_key: str | None = None) -> FileItem:
    return FileItem(
        source_path=path,
        source_type=source_type,
        order_index=order_index,
        ordering_key=ordering_key or path.as_posix().lower(),
    )


def _make_test_pdf(pdf_path: Path, page_sizes: tuple[tuple[int, int], ...] = ((300, 120), (200, 200))) -> None:
    images = [Image.new("RGB", size, color=(255, 255, 255)) for size in page_sizes]
    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)
    for image in images:
        image.close()


class _FakePdfiumError(Exception):
    pass


class _FakeImage:
    def __init__(self, size: tuple[int, int], save_log: list[tuple[Path, str]]):
        self.size = size
        self._save_log = save_log

    def save(self, output_path: Path, format: str) -> None:
        self._save_log.append((output_path, format))
        output_path.write_bytes(b"png")

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
        render_scales: list[float] | None = None,
        save_log: list[tuple[Path, str]] | None = None,
        close_log: list[str] | None = None,
        page_name: str = "page",
    ):
        self._size = size
        self._render_error = render_error
        self._render_scales = render_scales if render_scales is not None else []
        self._save_log = save_log if save_log is not None else []
        self._close_log = close_log if close_log is not None else []
        self._page_name = page_name

    def render(self, scale: float) -> _FakeBitmap:
        self._render_scales.append(scale)
        if self._render_error is not None:
            raise self._render_error
        return _FakeBitmap(_FakeImage(self._size, self._save_log))

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
def test_classify_pdfium_error_message_branches(message: str, expected: str) -> None:
    assert _classify_pdfium_error_message(message) == expected


def test_build_output_image_path_formats_expected_name(tmp_path: Path) -> None:
    source_pdf = tmp_path / "sample doc(1).pdf"
    output_dir = tmp_path / "im-temp"

    output_path = _build_output_image_path(source_pdf, page_number=7, output_dir=output_dir)

    assert output_path == output_dir / "sample doc(1)-p0007.png"


def test_rasterize_pdf_work_item_preserves_page_order_and_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample doc.pdf"
    output_dir = tmp_path / "im-temp"
    _make_test_pdf(pdf_path, page_sizes=((300, 120), (200, 200)))

    work_item = _make_work_item(pdf_path, order_index=3, ordering_key="manual-key")

    pages = rasterize_pdf_work_item(work_item=work_item, output_dir=output_dir)

    assert output_dir.exists()
    assert len(pages) == 2
    assert tuple(page.page_index for page in pages) == (0, 1)
    assert tuple(page.page_number for page in pages) == (1, 2)
    assert tuple(page.total_pages for page in pages) == (2, 2)
    assert tuple(page.source_index for page in pages) == (3, 3)
    assert tuple(page.source_ordering_key for page in pages) == ("manual-key", "manual-key")
    assert tuple(page.image_width for page in pages) == (600, 400)
    assert tuple(page.image_height for page in pages) == (240, 400)
    assert all(page.source_path == pdf_path for page in pages)
    assert all(page.image_path.exists() for page in pages)
    assert all(page.image_path.parent == output_dir for page in pages)
    assert pages[0].image_path.name.endswith("-p0001.png")
    assert pages[1].image_path.name.endswith("-p0002.png")


def test_rasterize_pdf_missing_source_maps_to_missing_input(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing.pdf"
    work_item = _make_work_item(missing_pdf)

    with pytest.raises(PdfRasterizationError) as exc_info:
        rasterize_pdf_work_item(work_item=work_item, output_dir=tmp_path / "im-temp")

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
def test_rasterize_pdf_open_failure_error_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str, expected_code: str) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((100, 100),))

    def _raise_on_open(_path: Path) -> None:
        raise _FakePdfiumError(message)

    monkeypatch.setattr(rasterizer.pdfium, "PdfiumError", _FakePdfiumError)
    monkeypatch.setattr(rasterizer.pdfium, "PdfDocument", _raise_on_open)

    with pytest.raises(PdfRasterizationError) as exc_info:
        rasterize_pdf_work_item(work_item=_make_work_item(pdf_path), output_dir=tmp_path / "im-temp")

    assert exc_info.value.error_code == expected_code
    assert exc_info.value.source_path == pdf_path


def test_rasterize_pdf_render_failure_closes_page_and_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    with pytest.raises(PdfRasterizationError) as exc_info:
        rasterize_pdf_work_item(
            work_item=_make_work_item(pdf_path),
            output_dir=tmp_path / "im-temp",
            render_scale=3.25,
        )

    assert exc_info.value.error_code == "corrupted_pdf"
    assert close_log == ["page-0.close", "document.close"]


def test_rasterize_pdf_work_item_zero_pages_returns_empty_and_closes_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((100, 100),))

    close_log: list[str] = []
    fake_document = _FakeDocument(pages=(), close_log=close_log)

    monkeypatch.setattr(rasterizer.pdfium, "PdfDocument", lambda _path: fake_document)

    pages = rasterize_pdf_work_item(
        work_item=_make_work_item(pdf_path),
        output_dir=tmp_path / "im-temp",
    )

    assert pages == ()
    assert close_log == ["document.close"]


def test_rasterize_pdf_work_item_forwards_render_scale_with_fake_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_test_pdf(pdf_path, page_sizes=((50, 40),))

    render_scales: list[float] = []
    save_log: list[tuple[Path, str]] = []
    close_log: list[str] = []
    page = _FakePage(
        size=(50, 40),
        render_scales=render_scales,
        save_log=save_log,
        close_log=close_log,
        page_name="page-0",
    )
    fake_document = _FakeDocument(pages=(page,), close_log=close_log)

    monkeypatch.setattr(rasterizer.pdfium, "PdfDocument", lambda _path: fake_document)

    pages = rasterize_pdf_work_item(
        work_item=_make_work_item(pdf_path, order_index=9, ordering_key="ok"),
        output_dir=tmp_path / "im-temp",
        render_scale=4.5,
    )

    assert len(pages) == 1
    assert render_scales == [4.5]
    assert save_log[0][1] == "PNG"
    assert close_log == ["page-0.close", "document.close"]


def test_rasterize_pdf_work_items_filters_non_pdf_and_flattens_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "im-temp"
    item_pdf_1 = _make_work_item(tmp_path / "a.pdf", source_type="pdf", order_index=1, ordering_key="a")
    item_png = _make_work_item(tmp_path / "b.png", source_type="image", order_index=2, ordering_key="b")
    item_pdf_2 = _make_work_item(tmp_path / "c.pdf", source_type="pdf", order_index=3, ordering_key="c")

    calls: list[tuple[str, Path, float]] = []

    def _stub_rasterize(work_item: FileItem, output_dir: Path, render_scale: float):
        calls.append((work_item.source_path.name, output_dir, render_scale))
        return (f"{work_item.source_path.stem}-p1",)

    monkeypatch.setattr(rasterizer, "rasterize_pdf_work_item", _stub_rasterize)

    pages = rasterize_pdf_work_items(
        work_items=(item_pdf_1, item_png, item_pdf_2),
        output_dir=out_dir,
        render_scale=3.5,
    )

    assert calls == [
        ("a.pdf", out_dir, 3.5),
        ("c.pdf", out_dir, 3.5),
    ]
    assert pages == ("a-p1", "c-p1")