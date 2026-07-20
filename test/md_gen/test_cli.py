from unittest.mock import patch

from PIL import Image

from md_gen.cli import build_parser, main
from md_gen.foundation import run_generation


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


def test_run_generation_emits_stage_batch_and_complete_events(monkeypatch, tmp_path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_dir.mkdir()
    image_path = source_dir / "scan.png"
    image_path.write_bytes(b"png")
    pdf_path = source_dir / "doc.pdf"
    pdf_path.write_bytes(b"pdf")
    events = []

    from common.config import AppConfig, ImageSettings, LlamaModelSettings, MdGenSettings, MdMrgSettings, PathSettings, PromptSettings, RuntimeSettings
    from md_gen.discovery import FileItem

    config = AppConfig(
        paths=PathSettings(source_dir=source_dir, output_dir=output_dir),
        md_gen=MdGenSettings(prompts=PromptSettings(summary_prompt_path=None, summary_prompt_text="summary"), image=ImageSettings(max_longest_edge_px=1540, token_threshold=4096)),
        ocr_model=LlamaModelSettings(endpoint_url="http://127.0.0.1:8080/v1", model_name="ocr", request_timeout_seconds=1, request_max_retries=0),
        language_model=LlamaModelSettings(endpoint_url="http://127.0.0.1:8081/v1", model_name="lang", request_timeout_seconds=1, request_max_retries=0),
        md_mrg=MdMrgSettings(score=PromptSettings(summary_prompt_path=None, summary_prompt_text="score")),
        runtime=RuntimeSettings(dry_run=False, overwrite=True),
    )
    items = [
        FileItem(source_path=image_path, source_type="image", order_index=0, ordering_key=("scan.png",)),
        FileItem(source_path=pdf_path, source_type="pdf", order_index=1, ordering_key=("doc.pdf",)),
    ]

    def fake_process_file(config, file_item, *, progress_callback=None, progress_context=None):
        if progress_context is not None:
            progress_context.completed_jobs += 1
            progress_context.markdown_count += 1
        return {
            "source_file_name": file_item.source_path.name,
            "file_type": file_item.source_type,
            "page_count": 1,
            "date_of_process": "2026-01-01T00:00:00+00:00",
            "summary": "summary",
            "markdown_file": f"{file_item.source_path.stem}.md",
            "status": "ok",
        }

    monkeypatch.setattr("md_gen.foundation.build_work_items", lambda config: items)
    monkeypatch.setattr("md_gen.foundation.rasterizer.get_pdf_page_count", lambda path: 3)
    monkeypatch.setattr("md_gen.foundation.process_file", fake_process_file)

    exit_code = run_generation(config, progress_callback=events.append)

    assert exit_code == 0
    assert [event.kind for event in events] == ["stage_start", "batch_persisted", "complete"]
    assert events[0].total_jobs == 4
    assert events[-1].markdown_count == 2
    assert (output_dir / "batch.json").is_file()
