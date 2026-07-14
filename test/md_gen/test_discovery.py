from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from md_gen.config import AppConfig, build_config_from_args
from md_gen.discovery import (
	_is_supported_file,
	_ordering_key,
	_print_discovery_status,
	_source_type_for_file,
	build_work_items,
	discover_supported_files,
	normalize_work_items,
)


def _make_args(source_dir: Path, output_dir: Path) -> SimpleNamespace:
	return SimpleNamespace(
		source=str(source_dir),
		output=str(output_dir),
		summary_prompt=None,
		ocr_model_endpoint=None,
		ocr_model_name=None,
		ocr_timeout_seconds=None,
		ocr_max_retries=None,
		language_model_endpoint=None,
		language_model_name=None,
		language_timeout_seconds=None,
		language_max_retries=None,
		max_longest_edge_px=None,
		token_threshold=None,
		dry_run=False,
		overwrite=False,
	)


def _make_config(tmp_path: Path, file_names: tuple[str, ...]) -> tuple[AppConfig, Path]:
	source_dir = tmp_path / "source"
	output_dir = tmp_path / "output"
	source_dir.mkdir(parents=True, exist_ok=True)
	output_dir.mkdir(parents=True, exist_ok=True)

	for name in file_names:
		path = source_dir / name
		path.parent.mkdir(parents=True, exist_ok=True)
		if name.endswith("/"):
			path.mkdir(parents=True, exist_ok=True)
			continue
		path.write_text("dummy", encoding="utf-8")

	args = _make_args(source_dir, output_dir)
	config = build_config_from_args(args)
	return config, source_dir


def test_ordering_key_uses_lowercase_filename_only() -> None:
	assert _ordering_key(Path("/x/Dir/File.PDF")) == "file.pdf"


def test_print_discovery_status_includes_optional_reason(capsys) -> None:
	file_path = Path(".").resolve() / "sample.pdf"

	_print_discovery_status(file_path, status="consumed")
	first_line = capsys.readouterr().out.strip()
	assert "DISCOVERY status=consumed" in first_line
	assert "reason=" not in first_line

	_print_discovery_status(file_path, status="skipped", reason="unsupported_extension")
	second_line = capsys.readouterr().out.strip()
	assert "DISCOVERY status=skipped" in second_line
	assert "reason=unsupported_extension" in second_line


def test_is_supported_file_handles_supported_unsupported_and_directory(tmp_path: Path) -> None:
	pdf_path = tmp_path / "doc.PDF"
	txt_path = tmp_path / "notes.txt"
	folder_path = tmp_path / "nested"

	pdf_path.write_text("x", encoding="utf-8")
	txt_path.write_text("x", encoding="utf-8")
	folder_path.mkdir()

	assert _is_supported_file(pdf_path)
	assert not _is_supported_file(txt_path)
	assert not _is_supported_file(folder_path)


def test_source_type_for_file_maps_pdf_and_images() -> None:
	assert _source_type_for_file(Path("a.PDF")) == "pdf"
	assert _source_type_for_file(Path("b.jpg")) == "image"
	assert _source_type_for_file(Path("c.png")) == "image"
	assert _source_type_for_file(Path("d.jpeg")) == "image"


def test_discover_supported_files_empty_directory_returns_empty(tmp_path: Path, capsys) -> None:
	config, _ = _make_config(tmp_path, tuple())

	discovered = discover_supported_files(config)

	assert discovered == tuple()
	assert capsys.readouterr().out == ""


def test_discover_supported_files_only_unsupported_files(tmp_path: Path, capsys) -> None:
	config, source_dir = _make_config(tmp_path, ("a.txt", "b.md"))

	discovered = discover_supported_files(config)

	assert discovered == tuple()
	output = capsys.readouterr().out
	assert f"path={(source_dir / 'a.txt').resolve()}" in output
	assert f"path={(source_dir / 'b.md').resolve()}" in output
	assert "reason=unsupported_extension" in output


def test_discover_supported_files_mixed_and_nested_entries(tmp_path: Path, capsys) -> None:
	config, source_dir = _make_config(
		tmp_path,
		("02-note.txt", "01-file.PDF", "03-photo.JPEG", "folder/"),
	)

	discovered = discover_supported_files(config)

	assert discovered == (
		(source_dir / "01-file.PDF").resolve(),
		(source_dir / "03-photo.JPEG").resolve(),
	)

	output = capsys.readouterr().out
	assert "status=consumed" in output
	assert "reason=unsupported_extension" in output
	assert "reason=not_a_file" in output


def test_discover_supported_files_is_ordered_case_insensitively(tmp_path: Path) -> None:
	config, source_dir = _make_config(tmp_path, ("b.PDF", "A.jpeg", "c.jpg"))

	discovered = discover_supported_files(config)

	assert discovered == (
		(source_dir / "A.jpeg").resolve(),
		(source_dir / "b.PDF").resolve(),
		(source_dir / "c.jpg").resolve(),
	)


def test_normalize_work_items_builds_ordered_records() -> None:
	files = (Path("B.JPG"), Path("a.PDF"))

	work_items = normalize_work_items(files)

	assert len(work_items) == 2
	assert work_items[0].source_path == Path("B.JPG")
	assert work_items[0].source_type == "image"
	assert work_items[0].order_index == 0
	assert work_items[0].ordering_key == "b.jpg"

	assert work_items[1].source_path == Path("a.PDF")
	assert work_items[1].source_type == "pdf"
	assert work_items[1].order_index == 1
	assert work_items[1].ordering_key == "a.pdf"


def test_build_work_items_orchestrates_discovery_and_normalization(tmp_path: Path) -> None:
	config, source_dir = _make_config(tmp_path, ("B.JPG", "a.pdf", "ignore.md"))

	work_items = build_work_items(config)

	assert len(work_items) == 2
	assert work_items[0].source_path == (source_dir / "a.pdf").resolve()
	assert work_items[0].source_type == "pdf"
	assert work_items[0].order_index == 0
	assert work_items[0].ordering_key == "a.pdf"

	assert work_items[1].source_path == (source_dir / "B.JPG").resolve()
	assert work_items[1].source_type == "image"
	assert work_items[1].order_index == 1
	assert work_items[1].ordering_key == "b.jpg"

