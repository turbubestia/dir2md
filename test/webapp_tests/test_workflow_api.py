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
from webapp.backend.workflow import WorkflowServiceError, _read_prompt
from md_gen.progress import GenerationProgressEvent
from md_mrg import apply as apply_mod
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
            "summary": {
                "system_prompt": "data/prompts/md_gen_summary_system_prompt.md",
                "assistant_prompt": "",
                "temperature": 0.7,
            },
            "image": {"max_longest_edge_px": 1540, "token_threshold": 4096},
        },
        "md_mrg": {
            "merge_score": {
                "system_prompt": "data/prompts/md_mrg_score_system_prompt.md",
                "assistant_prompt": "",
                "temperature": 0.7,
            },
            "merge_summary": {
                "system_prompt": "data/prompts/md_mrg_merge_summary_system_prompt.md",
                "assistant_prompt": "",
                "temperature": 0.7,
            },
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


def _wait_for_merge_state(client: TestClient, status: str, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/workflow/state").json()
        if state["merge_status"] == status:
            return state
        time.sleep(0.01)
    return client.get("/api/workflow/state").json()


def _encoded_id(relative_path: str) -> str:
    return base64.urlsafe_b64encode(relative_path.encode("utf-8")).decode("ascii").rstrip("=")


def _artifact_id(source_file_name: str, markdown_file: str) -> str:
    raw = json.dumps([source_file_name, markdown_file], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _image_doc(stem: str, **extra) -> dict:
    return {
        "source_file_name": f"{stem}.png",
        "file_type": "image",
        "markdown_file": f"{stem}.md",
        "page_count": 1,
        "date_of_process": "2026-07-18T00:00:00+00:00",
        "summary": f"Summary {stem}",
        "status": "ok",
        **extra,
    }


def _pdf_doc(stem: str, **extra) -> dict:
    return {
        "source_file_name": f"{stem}.pdf",
        "file_type": "pdf",
        "markdown_file": f"{stem}.md",
        "page_count": 3,
        "date_of_process": "2026-07-18T00:00:00+00:00",
        "summary": f"Summary {stem}",
        "status": "ok",
        **extra,
    }


def _write_merge_plan(output: Path, documents: list[dict]) -> None:
    output.mkdir(exist_ok=True)
    (output / "batch_mrg.json").write_text(json.dumps({"documents": documents}, indent=2), encoding="utf-8")


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


def test_merge_plan_loads_editable_groups_pdfs_and_metadata(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    first = _image_doc("page-1", confidence=0.92)
    second = _image_doc("page-2")
    pdf = _pdf_doc("report", category="invoice")
    _write_merge_plan(output, [{"documents": [first, second]}, pdf])
    _write_settings(settings_path, source, output)

    response = _client(settings_path, defaults_path).get("/api/workflow/merge-plan")

    assert response.status_code == 200
    data = response.json()
    assert [item["kind"] for item in data["items"]] == ["image_group", "pdf"]
    assert data["items"][0]["id"] == "group-1"
    assert data["items"][0]["display_name"] == "DocumentGroup_1"
    assert [document["kind"] for document in data["items"][0]["documents"]] == ["image_page", "image_page"]
    assert data["items"][0]["documents"][0]["confidence"] == 0.92
    assert data["items"][1]["category"] == "invoice"


def test_merge_plan_reports_missing_and_malformed_files(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    _write_settings(settings_path, source, output)
    client = _client(settings_path, defaults_path)

    assert client.get("/api/workflow/merge-plan").status_code == 404

    (output / "batch_mrg.json").write_text(json.dumps({"documents": [{"documents": []}]}), encoding="utf-8")
    malformed = client.get("/api/workflow/merge-plan")

    assert malformed.status_code == 400


def test_merge_plan_save_reorders_moves_and_omits_ui_fields(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    first = _image_doc("page-1", confidence=0.92)
    second = _image_doc("page-2")
    third = _image_doc("page-3")
    pdf = _pdf_doc("report")
    _write_merge_plan(output, [{"documents": [first, second]}, pdf, {"documents": [third]}])
    _write_settings(settings_path, source, output)
    client = _client(settings_path, defaults_path)
    plan = client.get("/api/workflow/merge-plan").json()
    first_group = plan["items"][0]
    pdf_item = plan["items"][1]
    second_group = plan["items"][2]
    moved_page = first_group["documents"].pop(1)
    second_group["documents"].insert(0, moved_page)
    new_group = {
        "id": "group-new",
        "kind": "image_group",
        "display_name": "DocumentGroup_New",
        "documents": [first_group["documents"].pop(0)],
    }
    plan["items"] = [pdf_item, second_group, new_group]

    response = client.put("/api/workflow/merge-plan", json=plan)

    assert response.status_code == 200
    saved = json.loads((output / "batch_mrg.json").read_text(encoding="utf-8"))
    assert saved["documents"][0]["source_file_name"] == "report.pdf"
    assert [document["source_file_name"] for document in saved["documents"][1]["documents"]] == ["page-2.png", "page-3.png"]
    assert [document["source_file_name"] for document in saved["documents"][2]["documents"]] == ["page-1.png"]
    serialized = json.dumps(saved)
    assert "image_group" not in serialized
    assert "display_name" not in serialized
    assert "group-new" not in serialized
    assert saved["documents"][2]["documents"][0]["confidence"] == 0.92


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["items"].__setitem__(0, {**plan["items"][0], "documents": []}),
        lambda plan: plan["items"][0]["documents"].__setitem__(1, {**plan["items"][0]["documents"][1], "id": plan["items"][0]["documents"][0]["id"]}),
        lambda plan: plan["items"][0]["documents"].__setitem__(0, {**plan["items"][1], "kind": "pdf"}),
        lambda plan: plan["items"].append({**plan["items"][0]["documents"][0], "kind": "image_page"}),
    ],
)
def test_merge_plan_save_rejects_invalid_payloads_without_mutating_file(workflow_paths, tmp_path: Path, mutate):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    _write_merge_plan(output, [{"documents": [_image_doc("page-1"), _image_doc("page-2")]}, _pdf_doc("report")])
    original = (output / "batch_mrg.json").read_text(encoding="utf-8")
    _write_settings(settings_path, source, output)
    client = _client(settings_path, defaults_path)
    plan = client.get("/api/workflow/merge-plan").json()
    mutate(plan)

    response = client.put("/api/workflow/merge-plan", json=plan)

    assert response.status_code == 400
    assert (output / "batch_mrg.json").read_text(encoding="utf-8") == original


def test_ocr_previews_use_source_files_and_markdown_uses_output_files(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    image_doc = _image_doc("page-1")
    pdf_doc = _pdf_doc("report")
    _write_merge_plan(output, [{"documents": [image_doc]}, pdf_doc])
    (source / "page-1.png").write_bytes(b"image bytes")
    (output / "page-1.md").write_text("# Page 1", encoding="utf-8")
    (source / "report.pdf").write_bytes(b"%PDF-1.4")
    (output / "report.md").write_text("# Report", encoding="utf-8")
    _write_settings(settings_path, source, output)
    client = _client(settings_path, defaults_path)

    image_id = _artifact_id("page-1.png", "page-1.md")
    pdf_id = _artifact_id("report.pdf", "report.md")
    image_preview = client.get(f"/api/workflow/ocr-preview/{image_id}")
    pdf_preview = client.get(f"/api/workflow/ocr-preview/{pdf_id}")
    markdown_preview = client.get(f"/api/workflow/markdown-preview/{image_id}")

    assert image_preview.status_code == 200
    assert image_preview.content == b"image bytes"
    assert pdf_preview.status_code == 200
    assert pdf_preview.content == b"%PDF-1.4"
    assert markdown_preview.status_code == 200
    assert markdown_preview.json() == {"id": image_id, "markdown_file": "page-1.md", "content": "# Page 1"}

    (source / "page-1.png").unlink()
    assert client.get(f"/api/workflow/ocr-preview/{image_id}").status_code == 404


def test_ocr_preview_rejects_traversal_artifact_paths(workflow_paths, tmp_path: Path):
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    _write_merge_plan(output, [{"documents": [_image_doc("page-1", source_file_name="../outside.png")]}])
    _write_settings(settings_path, source, output)

    response = _client(settings_path, defaults_path).get(
        f"/api/workflow/ocr-preview/{_artifact_id('../outside.png', 'page-1.md')}"
    )

    assert response.status_code == 400


def test_workflow_state_is_idle_before_start(workflow_paths) -> None:
    settings_path, defaults_path = workflow_paths

    response = _client(settings_path, defaults_path).get("/api/workflow/state")

    assert response.status_code == 200
    data = response.json()
    assert data["discovery"] is None
    assert data["ocr_status"] == "idle"
    assert data["merge_status"] == "idle"
    assert data["progress"]["percent"] == 0.0
    assert data["completed_item_ids"] == []


def test_merge_requires_completed_ocr(workflow_paths, tmp_path: Path) -> None:
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    _write_merge_plan(output, [_pdf_doc("report")])
    _write_settings(settings_path, source, output)
    client = _client(settings_path, defaults_path)
    plan = client.get("/api/workflow/merge-plan").json()

    response = client.post("/api/workflow/merge", json={"plan": plan})

    assert response.status_code == 400
    assert response.json()["detail"] == "Run OCR successfully before merge."


def test_merge_runs_apply_loads_results_and_serves_previews(workflow_paths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "report.pdf").write_bytes(b"source pdf")
    _write_settings(settings_path, source, output)
    plan_payload = {"documents": [_pdf_doc("report")]}

    def fake_generation(config, progress_callback=None):
        (output / "batch.json").write_text(json.dumps(plan_payload), encoding="utf-8")
        return 0

    monkeypatch.setattr("webapp.backend.workflow.md_gen_foundation.run_generation", fake_generation)
    def fake_plan(source_dir, cfg, *, progress_callback=None):
        (output / "batch_mrg.json").write_text(json.dumps(plan_payload), encoding="utf-8")
        return plan_payload

    monkeypatch.setattr("webapp.backend.workflow.md_mrg_planner.run_plan", fake_plan)

    def fake_apply(source_dir, cfg, *, progress_callback=None):
        assert source_dir == output.resolve()
        assert cfg.paths.source_dir == source.resolve()
        if progress_callback:
            progress_callback(apply_mod.ApplyProgressEvent(kind="stage_start", total_items=1))
            progress_callback(apply_mod.ApplyProgressEvent(kind="item_start", item_index=1, item_type="pdf", total_items=1))
        (output / "report.pdf").write_bytes(b"merged pdf")
        (output / "report.md").write_text("# Merged", encoding="utf-8")
        result_payload = {
            "items": [
                {
                    "item_index": 1,
                    "item_type": "pdf",
                    "status": "ok",
                    "output_pdf": "report.pdf",
                    "output_markdown": "report.md",
                    "summary": "Summary report",
                    "document": _pdf_doc("report"),
                }
            ]
        }
        (output / "batch_mrg_result.json").write_text(json.dumps(result_payload), encoding="utf-8")
        if progress_callback:
            progress_callback(apply_mod.ApplyProgressEvent(kind="item_complete", item_index=1, item_type="pdf", status="ok", total_items=1, completed_items=1, output_pdf="report.pdf", output_markdown="report.md"))
            progress_callback(apply_mod.ApplyProgressEvent(kind="result_persisted", total_items=1, completed_items=1))
            progress_callback(apply_mod.ApplyProgressEvent(kind="complete", total_items=1, completed_items=1))
        return result_payload

    monkeypatch.setattr("webapp.backend.workflow.md_mrg_apply.run_apply", fake_apply)
    client = _client(settings_path, defaults_path)
    client.post("/api/workflow/start")
    client.post("/api/workflow/ocr")
    assert _wait_for_state(client, "complete")["ocr_status"] == "complete"
    plan = client.get("/api/workflow/merge-plan").json()

    response = client.post("/api/workflow/merge", json={"plan": plan})

    assert response.status_code == 200
    assert response.json()["merge_status"] == "running"
    state = _wait_for_merge_state(client, "complete")
    assert state["ocr_status"] == "complete"
    assert state["merge_results_available"] is True
    assert state["merge_items"][0]["status"] == "done"
    results = client.get("/api/workflow/merge-results")
    assert results.status_code == 200
    item = results.json()["items"][0]
    assert item["label"] == "report.pdf"
    assert item["output_pdf"] == "report.pdf"
    assert client.get(f"/api/workflow/merge-result-preview/{item['id']}").content == b"merged pdf"
    assert client.get(f"/api/workflow/merge-result-markdown/{item['id']}").json()["content"] == "# Merged"
    assert client.get(f"/api/workflow/merge-result-preview/{_artifact_id('../outside.pdf', 'report.md')}").status_code == 400


def test_merge_marks_failed_when_result_file_is_missing(workflow_paths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "report.pdf").write_bytes(b"source pdf")
    _write_settings(settings_path, source, output)
    plan_payload = {"documents": [_pdf_doc("report")]}
    def fake_generation(config, progress_callback=None):
        (output / "batch.json").write_text(json.dumps(plan_payload), encoding="utf-8")
        return 0

    monkeypatch.setattr("webapp.backend.workflow.md_gen_foundation.run_generation", fake_generation)
    def fake_plan(source_dir, cfg, *, progress_callback=None):
        (output / "batch_mrg.json").write_text(json.dumps(plan_payload), encoding="utf-8")
        return plan_payload

    monkeypatch.setattr("webapp.backend.workflow.md_mrg_planner.run_plan", fake_plan)
    monkeypatch.setattr("webapp.backend.workflow.md_mrg_apply.run_apply", lambda source_dir, cfg, *, progress_callback=None: {"items": []})
    client = _client(settings_path, defaults_path)
    client.post("/api/workflow/start")
    client.post("/api/workflow/ocr")
    assert _wait_for_state(client, "complete")["ocr_status"] == "complete"
    plan = client.get("/api/workflow/merge-plan").json()

    response = client.post("/api/workflow/merge", json={"plan": plan})

    assert response.status_code == 200
    state = _wait_for_merge_state(client, "failed")
    assert state["ocr_status"] == "complete"
    assert state["merge_results_available"] is False
    assert state["merge_result_error"]["code"] == "merge_result_invalid"


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
        payload = {"documents": [
            {"documents": [{"source_file_name": "scan-1.png", "file_type": "image", "markdown_file": "scan-1.md"}]},
            {"source_file_name": "report.pdf", "file_type": "pdf", "markdown_file": "report.md"},
        ]}
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
    assert set(state["completed_item_ids"]) == {item["id"] for item in state["discovery"]["items"]}
    assert state["current_item"] is None
    assert state["active_comparison"] is None

    client.post("/api/workflow/start")
    reset_state = client.get("/api/workflow/state").json()
    assert reset_state["completed_item_ids"] == []


def test_ocr_reports_completed_items_while_running(workflow_paths, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path, defaults_path = workflow_paths
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "scan-1.png").write_bytes(b"png")
    (source / "scan-2.png").write_bytes(b"png")
    _write_settings(settings_path, source, output)
    first_item_done = threading.Event()
    release = threading.Event()

    def fake_generation(config, progress_callback=None):
        if progress_callback:
            progress_callback(GenerationProgressEvent(kind="stage_start", total_jobs=2))
            progress_callback(GenerationProgressEvent(kind="ocr_item_start", total_jobs=2, source_path=source / "scan-1.png", source_file_name="scan-1.png", source_type="image", page_number=1, markdown_path=output / "scan-1.md"))
            progress_callback(GenerationProgressEvent(kind="ocr_item_complete", total_jobs=2, completed_jobs=1, markdown_count=1, source_path=source / "scan-1.png", source_file_name="scan-1.png", source_type="image", page_number=1, markdown_path=output / "scan-1.md"))
        first_item_done.set()
        release.wait(timeout=2)
        (output / "batch.json").write_text(json.dumps({"documents": []}), encoding="utf-8")
        return 0

    monkeypatch.setattr("webapp.backend.workflow.md_gen_foundation.run_generation", fake_generation)
    monkeypatch.setattr("webapp.backend.workflow.md_mrg_planner.run_plan", lambda source_dir, cfg, *, progress_callback=None: (output / "batch_mrg.json").write_text('{"documents": []}', encoding="utf-8") or {"documents": []})
    client = _client(settings_path, defaults_path)
    discovery = client.post("/api/workflow/start").json()
    first_item_id = discovery["items"][0]["id"]
    assert client.post("/api/workflow/ocr").status_code == 200
    assert first_item_done.wait(timeout=2)

    running_state = client.get("/api/workflow/state").json()
    release.set()

    assert running_state["ocr_status"] == "running"
    assert running_state["completed_item_ids"] == [first_item_id]


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


def _llm_test_client(tmp_path: Path) -> tuple[TestClient, Path]:
    """Create a client whose settings live under tmp_path/data/config so temp prompts land in tmp_path/data/temp."""
    config_dir = tmp_path / "data" / "config"
    config_dir.mkdir(parents=True)
    settings_path = config_dir / "settings.json"
    defaults_path = config_dir / "settings-default.json"
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    defaults_path.write_text(json.dumps(_settings_payload()), encoding="utf-8")
    settings_path.write_text(json.dumps(_settings_payload(str(source), str(output))), encoding="utf-8")
    app = create_app(
        settings_path=settings_path,
        defaults_path=defaults_path,
        allowed_origins=["http://localhost:5173"],
    )
    return TestClient(app), tmp_path


def test_get_llm_test_prompt_returns_empty_for_missing_file(tmp_path: Path) -> None:
    client, _ = _llm_test_client(tmp_path)
    response = client.get("/api/llm-test-prompt/system")
    assert response.status_code == 200
    assert response.text == ""


def test_get_llm_test_prompt_returns_existing_text(tmp_path: Path) -> None:
    client, root = _llm_test_client(tmp_path)
    prompt_path = root / "data" / "temp" / "llm_test_user.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("hello user", encoding="utf-8")

    response = client.get("/api/llm-test-prompt/user")

    assert response.status_code == 200
    assert response.text == "hello user"


def test_get_llm_test_prompt_rejects_invalid_name(tmp_path: Path) -> None:
    client, _ = _llm_test_client(tmp_path)
    response = client.get("/api/llm-test-prompt/admin")
    assert response.status_code == 400


def test_put_llm_test_prompt_creates_temp_directory_and_writes_file(tmp_path: Path) -> None:
    client, root = _llm_test_client(tmp_path)
    prompt_path = root / "data" / "temp" / "llm_test_system.md"

    response = client.put(
        "/api/llm-test-prompt/system",
        content="system prompt text",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 200
    assert prompt_path.exists()
    assert prompt_path.read_text(encoding="utf-8") == "system prompt text"


def test_put_llm_test_prompt_rejects_invalid_name(tmp_path: Path) -> None:
    client, _ = _llm_test_client(tmp_path)
    response = client.put(
        "/api/llm-test-prompt/evil",
        content="x",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 400


def _wait_for_llm_test_state(client: TestClient, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/workflow/state").json()
        if state["llm_test_status"] in ("complete", "failed"):
            return state
        time.sleep(0.01)
    return client.get("/api/workflow/state").json()


def test_post_llm_test_starts_job_and_returns_running_state(tmp_path: Path) -> None:
    client, root = _llm_test_client(tmp_path)
    system_path = root / "data" / "temp" / "llm_test_system.md"
    user_path = root / "data" / "temp" / "llm_test_user.md"
    system_path.parent.mkdir(parents=True, exist_ok=True)
    system_path.write_text("system", encoding="utf-8")
    user_path.write_text("user", encoding="utf-8")

    response = client.post(
        "/api/workflow/llm-test",
        json={
            "system_path": str(system_path),
            "user_path": str(user_path),
            "assistant_path": "",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["llm_test_status"] == "running"


def test_post_llm_test_completes_with_mocked_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, root = _llm_test_client(tmp_path)
    system_path = root / "data" / "temp" / "llm_test_system.md"
    user_path = root / "data" / "temp" / "llm_test_user.md"
    system_path.parent.mkdir(parents=True, exist_ok=True)
    system_path.write_text("system", encoding="utf-8")
    user_path.write_text("user", encoding="utf-8")

    def fake_run(config, system, user, assistant):
        return "mocked response text"

    monkeypatch.setattr("webapp.backend.workflow.run_chat_return_text", fake_run)

    response = client.post(
        "/api/workflow/llm-test",
        json={
            "system_path": str(system_path),
            "user_path": str(user_path),
            "assistant_path": "",
        },
    )
    assert response.status_code == 200

    state = _wait_for_llm_test_state(client)
    assert state["llm_test_status"] == "complete"
    assert state["llm_test_result"]["text"] == "mocked response text"
    assert state["llm_test_result"]["error"] is None


def test_post_llm_test_fails_when_chat_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, root = _llm_test_client(tmp_path)
    system_path = root / "data" / "temp" / "llm_test_system.md"
    user_path = root / "data" / "temp" / "llm_test_user.md"
    system_path.parent.mkdir(parents=True, exist_ok=True)
    system_path.write_text("system", encoding="utf-8")
    user_path.write_text("user", encoding="utf-8")

    def fake_run(config, system, user, assistant):
        raise RuntimeError("mocked chat failure")

    monkeypatch.setattr("webapp.backend.workflow.run_chat_return_text", fake_run)

    response = client.post(
        "/api/workflow/llm-test",
        json={
            "system_path": str(system_path),
            "user_path": str(user_path),
            "assistant_path": "",
        },
    )
    assert response.status_code == 200

    state = _wait_for_llm_test_state(client)
    assert state["llm_test_status"] == "failed"
    assert state["llm_test_result"]["error"] is not None
    assert "mocked chat failure" in state["llm_test_result"]["error"]["message"]


def test_read_prompt_allows_missing_assistant_file(tmp_path: Path) -> None:
    system_path = tmp_path / "system.md"
    system_path.write_text("system prompt", encoding="utf-8")

    prompt = _read_prompt(str(system_path), str(tmp_path / "missing.md"), "test")

    assert prompt.system_path == str(system_path.resolve())
    assert prompt.system_text == "system prompt"
    assert prompt.assistant_path == ""
    assert prompt.assistant_text == ""


def test_read_prompt_rejects_missing_system_file(tmp_path: Path) -> None:
    with pytest.raises(WorkflowServiceError) as exc_info:
        _read_prompt(str(tmp_path / "missing.md"), "", "test")

    assert exc_info.value.status_code == 400
    assert "system prompt" in str(exc_info.value)


def test_read_prompt_rejects_empty_system_file(tmp_path: Path) -> None:
    system_path = tmp_path / "system.md"
    system_path.write_text("   \n", encoding="utf-8")

    with pytest.raises(WorkflowServiceError) as exc_info:
        _read_prompt(str(system_path), "", "test")

    assert exc_info.value.status_code == 400
    assert "empty" in str(exc_info.value).lower()