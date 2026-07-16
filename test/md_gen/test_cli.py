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


def test_cli_parser_accepts_verbose_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--source", "in", "--output", "out", "--verbose"])

    assert args.verbose is True


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


def test_cli_verbose_prints_dump_before_bootstrap(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "md-gen",
            "--source",
            "C:/input",
            "--output",
            "C:/output",
            "--verbose",
        ],
    )

    order: list[str] = []

    def fake_build_config_from_args(args):
        order.append("build_config")
        return object()

    def fake_format_config_dump(config):
        order.append("format_dump")
        return "formatted config"

    def fake_print(*args, **kwargs):
        if args and args[0] == "formatted config":
            order.append("print_dump")

    def fake_bootstrap(config):
        order.append("bootstrap")
        return 0

    monkeypatch.setattr("md_gen.cli.build_config_from_args", fake_build_config_from_args)
    monkeypatch.setattr("md_gen.cli.format_config_dump", fake_format_config_dump)
    monkeypatch.setattr("md_gen.cli.run_foundation_bootstrap", fake_bootstrap)
    monkeypatch.setattr("builtins.print", fake_print)

    exit_code = main()

    assert exit_code == 0
    assert order == ["build_config", "format_dump", "print_dump", "bootstrap"]


def test_cli_non_verbose_does_not_format_dump(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "md-gen",
            "--source",
            "C:/input",
            "--output",
            "C:/output",
        ],
    )

    def fake_build_config_from_args(args):
        return object()

    def fail_format_config_dump(config):
        raise AssertionError("format_config_dump must not be called when --verbose is absent")

    monkeypatch.setattr("md_gen.cli.build_config_from_args", fake_build_config_from_args)
    monkeypatch.setattr("md_gen.cli.format_config_dump", fail_format_config_dump)
    monkeypatch.setattr("md_gen.cli.run_foundation_bootstrap", lambda config: 0)

    exit_code = main()

    assert exit_code == 0
