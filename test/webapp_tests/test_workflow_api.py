"""Tests for the webapp workflow discovery API."""

from __future__ import annotations

import base64
import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webapp.backend.app import create_app
from md_gen.progress import GenerationProgressEvent
from md_mrg.planner import PlanningProgressEvent


def _settings_payload(source_folder: str = "", output_folder: str = "") -> dict:
    return {
        "app_name": "dir2md",
        "version": "0.1.0",
        "source_folder": source_folder,
        "output_folder": output_folder,
        "verbose": False,
        "overwrite": False,
        "ocr_model": {
            "endpoint": "http://127.0.0.1:8080/v1/chat/completions",
            "model": "lightonocr-2",
            "timeout_seconds": 120,
            "max_retries": 3,
        },
        "language_model": {
            "endpoint": "http://127.0.0.1:8081/v1/chat/completions",
            "model": "qwen3-1.7b",
            "timeout_seconds": 120,
            "max_retries": 3,
        },
        "md_gen": {
            "summary": {"prompt_path": "data/prompts/md_gen_summary_system_prompt.md"},
            "image": {"max_longest_edge_px": 1540, "token_threshold": 4096},
        },
        "md_mrg": {
            "score": {"prompt_path": "data/prompts/md_mrg_score_system_prompt.md"},
        },
    }


@pytest.fixture
def workflow_paths(tmp_path: Path):
    settings_path = tmp_path / "settings.json"
    defaults_path = tmp_path / "settings-default.json"
    defaults_path.write_text(json.dumps(_settings_payload()), encoding="utf-8")
    return settings_path, defaults_path


def _client(settings_path: Path, defaults_path: Path) -> TestClient:
    app = create_app(
        settings_path=settings_path,
        defaults_path=defaults_path,
        allowed_origins=["http://localhost:5173"],
    )
    return TestClient(app)


def _write_settings(settings_path: Path, source: Path | str, output: Path | str = "") -> None:
    settings_path.write_text(
        json.dumps(_settings_payload(str(source), str(output))),
        encoding="utf-8",
    )


def _wait_for_state(client: TestClient, status: str, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/workflow/state").json()
        if state["ocr_status"] == status:
            return state
        time.sleep(0.01)
    return client.get("/api/workflow/state").json()


def _encoded_id(relative_path: str) -> str:
    return base64.urlsafe_b64encode(relative_path.encode("utf-8")).decode("ascii").rstrip("=")


def test_start_discovers_supported_sources_in_natural_order(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "page10.pdf").write_bytes(b"pdf")
    (source / "page2.png").write_bytes(b"png")
    (source / "page1.JPG").write_bytes(b"jpg")
    (source / "notes.txt").write_text("skip", encoding="utf-8")
    (source / "nested").mkdir()
    _write_settings(settings_path, source, output)

    response = _client(settings_path, defaults_path).post("/api/workflow/start")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source_status"]["status"] == "ready"
    assert data["output_status"]["status"] == "empty"
    assert data["metrics"] == {"pdf_count": 1, "image_count": 2, "total_count": 3}
    assert [item["display_name"] for item in data["items"]] == [
        "page1.JPG",
        "page2.png",
        "page10.pdf",
    ]
    assert [item["order_index"] for item in data["items"]] == [0, 1, 2]
    image_items = [item for item in data["items"] if item["source_type"] == "image"]
    pdf_items = [item for item in data["items"] if item["source_type"] == "pdf"]
    assert all(item["preview_url"] for item in image_items)
    assert pdf_items[0]["preview_url"]


@pytest.mark.parametrize("files", [[], ["notes.txt", "archive.zip"]])
def test_start_allows_zero_supported_items(workflow_paths, tmp_path: Path, files: list[str]):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    source.mkdir()
    for filename in files:
        (source / filename).write_text("skip", encoding="utf-8")
    _write_settings(settings_path, source, tmp_path / "missing-output")

    response = _client(settings_path, defaults_path).post("/api/workflow/start")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["metrics"]["total_count"] == 0
    assert data["items"] == []
    assert data["messages"][0]["severity"] == "warning"
    assert data["output_status"]["status"] == "missing"
    assert not (tmp_path / "missing-output").exists()


@pytest.mark.parametrize(
    ("source_value", "expected_status"),
    [
        ("", "not_configured"),
        ("missing", "missing"),
        ("file", "not_directory"),
    ],
)
def test_start_reports_invalid_source_statuses(
    workflow_paths,
    tmp_path: Path,
    source_value: str,
    expected_status: str,
):
    settings_path, defaults_path = workflow_paths
    source_path = ""
    if source_value == "missing":
        source_path = str(tmp_path / "does-not-exist")
    elif source_value == "file":
        source_file = tmp_path / "source.txt"
        source_file.write_text("not a directory", encoding="utf-8")
        source_path = str(source_file)
    _write_settings(settings_path, source_path, "")

    response = _client(settings_path, defaults_path).post("/api/workflow/start")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["source_status"]["status"] == expected_status
    assert data["metrics"]["total_count"] == 0


def test_start_reports_output_folder_statuses(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    source.mkdir()
    (source / "scan.pdf").write_bytes(b"pdf")
    output_file = tmp_path / "output.txt"
    output_file.write_text("not directory", encoding="utf-8")
    _write_settings(settings_path, source, output_file)

    file_response = _client(settings_path, defaults_path).post("/api/workflow/start")
    assert file_response.json()["output_status"]["status"] == "not_directory"

    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.md").write_text("content", encoding="utf-8")
    _write_settings(settings_path, source, output)

    ready_response = _client(settings_path, defaults_path).post("/api/workflow/start")
    output_status = ready_response.json()["output_status"]
    assert output_status["status"] == "ready"
    assert output_status["item_count"] == 1
    assert (output / "existing.md").read_text(encoding="utf-8") == "content"


def test_valid_image_preview_returns_file_bytes(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    source.mkdir()
    (source / "scan.png").write_bytes(b"image bytes")
    _write_settings(settings_path, source, tmp_path / "output")
    client = _client(settings_path, defaults_path)
    discovery = client.post("/api/workflow/start").json()

    response = client.get(discovery["items"][0]["preview_url"])

    assert response.status_code == 200
    assert response.content == b"image bytes"
    assert response.headers["content-type"].startswith("image/")


def test_valid_pdf_preview_returns_file_bytes(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    source.mkdir()
    (source / "scan.pdf").write_bytes(b"pdf bytes")
    _write_settings(settings_path, source, tmp_path / "output")
    client = _client(settings_path, defaults_path)
    discovery = client.post("/api/workflow/start").json()

    response = client.get(discovery["items"][0]["preview_url"])

    assert response.status_code == 200
    assert response.content == b"pdf bytes"
    assert response.headers["content-type"].startswith("application/pdf")


def test_preview_rejects_unsupported_traversal_outside_and_missing(
    workflow_paths,
    tmp_path: Path,
):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    source.mkdir()
    (source / "scan.pdf").write_bytes(b"pdf bytes")
    (source / "notes.txt").write_bytes(b"secret text")
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside bytes")
    _write_settings(settings_path, source, tmp_path / "output")
    client = _client(settings_path, defaults_path)

    cases = [
        (_encoded_id("notes.txt"), 404),
        (_encoded_id("../outside.png"), 400),
        (_encoded_id(outside.as_posix()), 400),
        (_encoded_id("missing.png"), 404),
    ]
    for file_id, expected_status in cases:
        response = client.get(f"/api/workflow/source-preview/{file_id}")
        assert response.status_code == expected_status
        assert b"outside bytes" not in response.content
        assert b"secret text" not in response.content


def test_workflow_state_is_idle_before_start(workflow_paths) -> None:
    settings_path, defaults_path = workflow_paths

    response = _client(settings_path, defaults_path).get("/api/workflow/state")

    assert response.status_code == 200
    data = response.json()
    assert data["discovery"] is None
    assert data["ocr_status"] == "idle"
    assert data["progress"]["percent"] == 0.0


def test_ocr_requires_successful_non_empty_start(workflow_paths) -> None:
    settings_path, defaults_path = workflow_paths

    client = _client(settings_path, defaults_path)

    response = client.post("/api/workflow/ocr")

    assert response.status_code == 400


def test_ocr_runs_generation_then_planning_and_updates_state(workflow_paths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "scan-1.png").write_bytes(b"png")
    (source / "scan-2.png").write_bytes(b"png")
    _write_settings(settings_path, source, output)

    def fake_generation(config, progress_callback=None):
        if progress_callback:
            progress_callback(GenerationProgressEvent(kind="stage_start", total_jobs=2))
            progress_callback(GenerationProgressEvent(kind="ocr_item_start", total_jobs=2, source_path=source / "scan-1.png", source_file_name="scan-1.png", source_type="image", page_number=1, markdown_path=output / "scan-1.md"))
            progress_callback(GenerationProgressEvent(kind="ocr_item_complete", total_jobs=2, completed_jobs=1, markdown_count=1, source_path=source / "scan-1.png", source_file_name="scan-1.png", source_type="image", page_number=1, markdown_path=output / "scan-1.md"))
            progress_callback(GenerationProgressEvent(kind="batch_persisted", total_jobs=2, completed_jobs=2, markdown_count=2, markdown_path=output / "batch.json"))
        (output / "batch.json").write_text(json.dumps({"documents": [
            {"source_file_name": "scan-1.png", "file_type": "image", "markdown_file": "scan-1.md"},
            {"source_file_name": "report.pdf", "file_type": "pdf", "markdown_file": "report.md"},
        ]}), encoding="utf-8")
        return 0

    def fake_plan(source_dir, cfg, *, progress_callback=None):
        if progress_callback:
            progress_callback(PlanningProgressEvent(kind="plan_start", total_comparisons=1, pdf_document_count=1))
            progress_callback(PlanningProgressEvent(kind="comparison_start", total_comparisons=1, left_display_name="scan-1.png", right_display_name="scan-2.png", pdf_document_count=1))
            progress_callback(PlanningProgressEvent(kind="comparison_complete", total_comparisons=1, completed_comparisons=1, left_display_name="scan-1.png", right_display_name="scan-2.png", score_status="scored", score=7, pdf_document_count=1))
            progress_callback(PlanningProgressEvent(kind="plan_persisted", total_comparisons=1, completed_comparisons=1, pdf_document_count=1, image_group_count=1))
        payload = {"documents": [{"documents": []}, {"source_file_name": "report.pdf", "file_type": "pdf"}]}
        (output / "batch_mrg.json").write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("webapp.backend.workflow.md_gen_foundation.run_generation", fake_generation)
    monkeypatch.setattr("webapp.backend.workflow.md_mrg_planner.run_plan", fake_plan)
    client = _client(settings_path, defaults_path)
    client.post("/api/workflow/start")

    response = client.post("/api/workflow/ocr")
    assert response.status_code == 200
    assert response.json()["ocr_status"] == "running"

    state = _wait_for_state(client, "complete")
    assert state["ocr_status"] == "complete"
    assert state["progress"]["percent"] == 100.0
    assert state["counts"] == {"markdown_count": 2, "pdf_document_count": 1, "image_group_count": 1}
    assert state["current_item"] is None
    assert state["active_comparison"] is None


def test_ocr_conflict_while_running(workflow_paths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "scan.png").write_bytes(b"png")
    _write_settings(settings_path, source, output)
    release = threading.Event()

    def fake_generation(config, progress_callback=None):
        if progress_callback:
            progress_callback(GenerationProgressEvent(kind="stage_start", total_jobs=1))
        release.wait(timeout=2)
        (output / "batch.json").write_text(json.dumps({"documents": []}), encoding="utf-8")
        return 0

    monkeypatch.setattr("webapp.backend.workflow.md_gen_foundation.run_generation", fake_generation)
    monkeypatch.setattr("webapp.backend.workflow.md_mrg_planner.run_plan", lambda source_dir, cfg, *, progress_callback=None: (output / "batch_mrg.json").write_text('{"documents": []}', encoding="utf-8") or {"documents": []})
    client = _client(settings_path, defaults_path)
    client.post("/api/workflow/start")
    assert client.post("/api/workflow/ocr").status_code == 200

    conflict = client.post("/api/workflow/ocr")
    release.set()

    assert conflict.status_code == 409


def test_workflow_events_streams_current_state_first(workflow_paths) -> None:
    settings_path, defaults_path = workflow_paths
    client = _client(settings_path, defaults_path)

    response = client.get("/api/workflow/events?once=true")

    assert response.status_code == 200
    lines = response.text.splitlines()
    assert lines[0] == "event: workflow_state"
    data_line = lines[1]
    assert data_line.startswith("data: ")
    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["ocr_status"] == "idle"