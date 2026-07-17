import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from common.config import AppConfig, ImageSettings, LlamaModelSettings, MdGenSettings, MdMrgSettings, PathSettings, PromptSettings, RuntimeSettings
from common.gateway import TextResponse
from md_mrg.cli import build_parser
from md_mrg import planner as planner_mod


def _doc(name: str, file_type: str = "image") -> dict:
    return {
        "source_file_name": name,
        "file_type": file_type,
        "page_count": 1,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "summary",
        "markdown_file": f"{Path(name).stem}.md",
        "status": "ok",
    }


def _cfg(source_dir: Path) -> AppConfig:
    return AppConfig(
        paths=PathSettings(source_dir=source_dir, output_dir=source_dir),
        ocr_model=LlamaModelSettings(
            endpoint_url="http://localhost:8080/v1/chat/completions",
            model_name="ocr-model",
            request_timeout_seconds=30.0,
            request_max_retries=0,
        ),
        language_model=LlamaModelSettings(
            endpoint_url="http://localhost:8081/v1/chat/completions",
            model_name="qwen3-1.7b",
            request_timeout_seconds=30.0,
            request_max_retries=0,
        ),
        md_gen=MdGenSettings(
            prompts=PromptSettings(summary_prompt_path=None, summary_prompt_text="summary"),
            image=ImageSettings(max_longest_edge_px=1540, token_threshold=4096),
        ),
        md_mrg=MdMrgSettings(
            score=PromptSettings(
                summary_prompt_path=source_dir / "score_prompt.md",
                summary_prompt_text="Return JSON with score key.",
            ),
        ),
        runtime=RuntimeSettings(dry_run=False, overwrite=False),
    )


def _write_batch(source_dir: Path, docs: list[dict]) -> None:
    (source_dir / "batch.json").write_text(json.dumps({"documents": docs}, indent=2), encoding="utf-8")


def _write_markdowns(source_dir: Path, docs: list[dict]) -> None:
    for doc in docs:
        markdown_file = doc.get("markdown_file")
        if markdown_file:
            (source_dir / markdown_file).write_text(f"content-{markdown_file}", encoding="utf-8")


def test_cli_requires_exactly_one_mode() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as missing_mode:
        parser.parse_args(["--source", "./out"])
    assert missing_mode.value.code == 2

    with pytest.raises(SystemExit) as both_modes:
        parser.parse_args(["--source", "./out", "--plan", "--apply"])
    assert both_modes.value.code == 2


def test_planner_groups_images_and_appends_pdf_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    images = [_doc(f"img-{n}.jpg") for n in range(1, 6)]
    pdfs = [_doc("booklet.pdf", file_type="pdf"), _doc("report.pdf", file_type="pdf")]
    all_docs = images + pdfs

    _write_batch(source_dir, all_docs)
    _write_markdowns(source_dir, all_docs)

    scores = iter(["{\"score\": 6}", "{\"score\": 8}", "{\"score\": 2}", "{\"score\": 7}"])

    class FakeGateway:
        def __init__(self, endpoint_url: str, model_name: str):
            self.endpoint_url = endpoint_url
            self.model_name = model_name
            self.request_timeout_seconds = 0.0
            self.request_max_retries = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def send_text_request(self, request):
            return TextResponse(model_name=self.model_name, text=next(scores), raw_response={})

    monkeypatch.setattr(planner_mod, "LlamaLanguageGateway", FakeGateway)

    out = planner_mod.run_plan(source_dir=source_dir, cfg=_cfg(source_dir))

    documents = out["documents"]
    assert len(documents) == 4
    assert documents[0]["documents"] == [images[0], images[1], images[2]]
    assert documents[1]["documents"] == [images[3], images[4]]
    assert documents[2] == pdfs[0]
    assert documents[3] == pdfs[1]

    captured = capsys.readouterr()
    assert captured.out == (
        "img-1.jpg <=> img-2.jpg == 6.0 \n"
        "img-2.jpg <=> img-3.jpg == 8.0 \n"
        "img-3.jpg <=> img-4.jpg == 2.0 \n"
        "img-4.jpg <=> img-5.jpg == 7.0 \n"
    )

    plan_file_payload = json.loads((source_dir / "batch_mrg.json").read_text(encoding="utf-8"))
    assert plan_file_payload == out


def test_planner_reorders_group_when_score_is_negative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    images = [_doc(f"img-{n}.jpg") for n in range(1, 5)]
    _write_batch(source_dir, images)
    _write_markdowns(source_dir, images)

    scores = iter(["{\"score\": 6}", "{\"score\": -6}", "{\"score\": 8}"])

    class FakeGateway:
        def __init__(self, endpoint_url: str, model_name: str):
            self.request_timeout_seconds = 0.0
            self.request_max_retries = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def send_text_request(self, request):
            return TextResponse(model_name="m", text=next(scores), raw_response={})

    monkeypatch.setattr(planner_mod, "LlamaLanguageGateway", FakeGateway)

    out = planner_mod.run_plan(source_dir=source_dir, cfg=_cfg(source_dir))
    documents = out["documents"]

    assert len(documents) == 1
    assert documents[0]["documents"] == [images[0], images[2], images[1], images[3]]


def test_planner_splits_group_on_score_parse_failure_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    images = [_doc(f"img-{n}.jpg") for n in range(1, 4)]
    _write_batch(source_dir, images)
    _write_markdowns(source_dir, images)

    scores = iter(["not-json", "{\"score\": 7}"])

    class FakeGateway:
        def __init__(self, endpoint_url: str, model_name: str):
            self.request_timeout_seconds = 0.0
            self.request_max_retries = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def send_text_request(self, request):
            return TextResponse(model_name="m", text=next(scores), raw_response={})

    monkeypatch.setattr(planner_mod, "LlamaLanguageGateway", FakeGateway)

    out = planner_mod.run_plan(source_dir=source_dir, cfg=_cfg(source_dir))
    documents = out["documents"]

    assert len(documents) == 2
    assert documents[0]["documents"] == [images[0]]
    assert documents[1]["documents"] == [images[1], images[2]]


def test_cli_main_dispatches_plan_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    called = {"plan": False}

    def fake_build_cfg(args: SimpleNamespace) -> AppConfig:
        return _cfg(source_dir)

    def fake_run_plan(source_dir: Path, cfg: AppConfig) -> dict:
        called["plan"] = True
        return {"documents": []}

    monkeypatch.setattr("md_mrg.cli.build_md_mrg_config_from_args", fake_build_cfg)
    monkeypatch.setattr("md_mrg.cli.run_plan", fake_run_plan)
    monkeypatch.setattr("sys.argv", ["md-mrg", "--source", str(source_dir), "--plan"])

    from md_mrg.cli import main

    assert main() == 0
    assert called["plan"] is True
