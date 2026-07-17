"""Tests for the webapp FastAPI settings API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webapp.backend.app import create_app


@pytest.fixture
def tmp_settings_paths(tmp_path: Path):
    """Provide isolated settings and defaults files plus a configured app."""
    defaults = tmp_path / "settings-default.json"
    defaults.write_text(
        json.dumps(
            {
                "app_name": "dir2md",
                "version": "0.1.0",
                "source_folder": "",
                "output_folder": "",
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
                        "prompt_path": "data/prompts/md_gen_summary_system_prompt.md",
                    },
                    "image": {
                        "max_longest_edge_px": 1540,
                        "token_threshold": 4096,
                    },
                },
                "md_mrg": {
                    "score": {
                        "prompt_path": "data/prompts/md_mrg_score_system_prompt.md",
                    },
                },
            },
            indent=4,
        ),
        encoding="utf-8",
    )
    settings = tmp_path / "settings.json"
    return settings, defaults


@pytest.fixture
def client(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    app = create_app(
        settings_path=settings_path,
        defaults_path=defaults_path,
        allowed_origins=["http://localhost:5173"],
    )
    return TestClient(app)


@pytest.fixture
def valid_payload():
    return {
        "app_name": "dir2md",
        "version": "0.1.0",
        "source_folder": "C:\\source",
        "output_folder": "C:\\output",
        "verbose": True,
        "overwrite": True,
        "ocr_model": {
            "endpoint": "http://192.168.1.147:8080/v1/chat/completions",
            "model": "lightonocr-2",
            "timeout_seconds": 120,
            "max_retries": 3,
        },
        "language_model": {
            "endpoint": "http://192.168.1.147:8081/v1/chat/completions",
            "model": "qwen3-1.7b",
            "timeout_seconds": 120,
            "max_retries": 3,
        },
        "md_gen": {
            "summary": {
                "prompt_path": "data/prompts/md_gen_summary_system_prompt.md",
            },
            "image": {
                "max_longest_edge_px": 1540,
                "token_threshold": 4096,
            },
        },
        "md_mrg": {
            "score": {
                "prompt_path": "data/prompts/md_mrg_score_system_prompt.md",
            },
        },
    }


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_settings_returns_full_document(client, tmp_settings_paths, valid_payload):
    settings_path, defaults_path = tmp_settings_paths
    settings_path.write_text(json.dumps(valid_payload), encoding="utf-8")

    response = client.get("/api/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["source_folder"] == "C:\\source"
    assert data["output_folder"] == "C:\\output"
    assert "ocr_model" in data
    assert "md_gen" in data
    assert "md_mrg" in data


def test_put_settings_updates_file(client, tmp_settings_paths, valid_payload):
    settings_path, _ = tmp_settings_paths

    response = client.put("/api/settings", json=valid_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["source_folder"] == "C:\\source"
    assert data["output_folder"] == "C:\\output"
    disk = json.loads(settings_path.read_text(encoding="utf-8"))
    assert disk["source_folder"] == "C:\\source"
    assert disk["output_folder"] == "C:\\output"
    assert disk["verbose"] is True
    assert disk["overwrite"] is True


def test_put_settings_invalid_endpoint_returns_422(client, valid_payload):
    invalid_payload = json.loads(json.dumps(valid_payload))
    invalid_payload["ocr_model"]["endpoint"] = "not-a-url"

    response = client.put("/api/settings", json=invalid_payload)

    assert response.status_code == 422
    assert "detail" in response.json()


def test_put_settings_missing_section_returns_422(client, valid_payload):
    invalid_payload = json.loads(json.dumps(valid_payload))
    del invalid_payload["md_gen"]

    response = client.put("/api/settings", json=invalid_payload)

    assert response.status_code == 422


def test_cors_preflight(client):
    response = client.options(
        "/api/settings",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_openapi_docs_available(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
