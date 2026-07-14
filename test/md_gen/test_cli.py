from unittest.mock import patch

from PIL import Image

from md_gen.cli import build_parser, main


def test_cli_requires_source_and_output() -> None:
    parser = build_parser()
    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected parser failure when required arguments are missing")


def test_cli_bootstrap_creates_output_and_batch_json(monkeypatch, tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"

    source_file = source_dir / "sample.png"
    image = Image.new("RGB", (50, 50), color=(255, 255, 255))
    image.save(source_file)
    image.close()

    monkeypatch.setattr(
        "sys.argv",
        [
            "md-gen",
            "--source",
            str(source_dir),
            "--output",
            str(output_dir),
        ],
    )

    with patch("md_gen.foundation.process_file") as mock_process_file:
        mock_process_file.return_value = {
            "source_file_name": "sample.png",
            "file_type": "image",
            "page_count": 1,
            "date_of_process": "2026-01-01T00:00:00+00:00",
            "summary": "summary",
            "markdown_file": "sample.md",
            "status": "ok",
        }
        exit_code = main()

    assert exit_code == 0
    assert output_dir.is_dir()
    assert (output_dir / "batch.json").is_file()
    mock_process_file.assert_called_once()
