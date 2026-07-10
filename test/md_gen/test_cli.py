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


def test_cli_bootstrap_creates_output_temp_directories(monkeypatch, tmp_path) -> None:
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
            "--dry-run",
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert (output_dir / "temp" / "images").is_dir()
    assert (output_dir / "temp" / "markdown").is_dir()
    assert (output_dir / "temp" / "metadata").is_dir()
