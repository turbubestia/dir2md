from argparse import Namespace
from pathlib import Path

from md_gen.config import build_config_from_args
from md_gen.discovery import build_work_items


def _build_args(source: list[str], source_list_file: list[str]) -> Namespace:
    return Namespace(
        source=source,
        source_list_file=source_list_file,
        output_dir=None,
        im_temp_dir=None,
        md_temp_dir=None,
        log_file=None,
        model_endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        request_timeout_seconds=120.0,
        request_max_retries=2,
        max_longest_edge_px=1540,
        token_threshold=16000,
        dry_run=True,
        overwrite=False,
    )


def test_discovery_from_directory_single_and_list_file_is_deterministic(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    nested_dir = image_dir / "nested"
    image_dir.mkdir()
    nested_dir.mkdir()

    dir_pdf = image_dir / "z.pdf"
    dir_image = nested_dir / "a.JPG"
    ignored_file = nested_dir / "ignore.txt"
    single_image = tmp_path / "single.png"

    dir_pdf.touch()
    dir_image.touch()
    ignored_file.touch()
    single_image.touch()

    list_file = tmp_path / "sources.txt"
    list_file.write_text(
        "\n".join(
            [
                "# comment",
                str(single_image),
                str(dir_pdf),
                "",
            ]
        ),
        encoding="utf-8",
    )

    args = _build_args(
        source=[str(image_dir), str(single_image)],
        source_list_file=[str(list_file)],
    )
    config = build_config_from_args(args)

    work_items = build_work_items(config)

    assert tuple(item.source_path for item in work_items) == (
        dir_image.resolve(),
        dir_pdf.resolve(),
        single_image.resolve(),
    )
    assert tuple(item.source_type for item in work_items) == ("image", "pdf", "image")
    assert tuple(item.order_index for item in work_items) == (0, 1, 2)


def test_discovery_raises_when_input_path_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"
    args = _build_args(source=[str(missing)], source_list_file=[])
    config = build_config_from_args(args)

    try:
        build_work_items(config)
    except FileNotFoundError as exc:
        assert str(missing.resolve()) in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing path")


def test_discovery_excludes_generated_artifact_directories(tmp_path: Path) -> None:
    source_dir = tmp_path / "data"
    source_dir.mkdir()

    source_image = source_dir / "scan.jpg"
    source_image.touch()

    im_temp_dir = source_dir / "im-temp"
    md_temp_dir = source_dir / "md-temp"
    output_dir = source_dir / "output"
    logs_dir = source_dir / "logs"

    im_temp_dir.mkdir()
    md_temp_dir.mkdir()
    output_dir.mkdir()
    logs_dir.mkdir()

    (im_temp_dir / "scan-processed.jpg").touch()
    (md_temp_dir / "scan-processed.png").touch()
    (output_dir / "report.pdf").touch()
    (logs_dir / "from_logs.jpg").touch()

    args = _build_args(source=[str(source_dir)], source_list_file=[])
    config = build_config_from_args(args)

    work_items = build_work_items(config)

    assert tuple(item.source_path for item in work_items) == (source_image.resolve(),)
