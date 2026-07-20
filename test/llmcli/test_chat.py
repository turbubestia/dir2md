from __future__ import annotations

import json
from pathlib import Path

import llmcli.chat as chat
from common.config import (
    AppConfig,
    ImageSettings,
    LlamaModelSettings,
    MdGenSettings,
    MdMrgSettings,
    PathSettings,
    PromptSettings,
    RuntimeSettings,
)
from common.gateway import TextResponse


def _make_config(output_dir: Path) -> AppConfig:
    return AppConfig(
        paths=PathSettings(source_dir=Path(), output_dir=output_dir),
        ocr_model=LlamaModelSettings(
            endpoint_url="http://ocr",
            model_name="ocr",
            request_timeout_seconds=30.0,
            request_max_retries=2,
            temperature=0.7,
            top_p=0.9,
            top_k=0,
            min_p=0.05,
        ),
        language_model=LlamaModelSettings(
            endpoint_url="http://lang",
            model_name="lang",
            request_timeout_seconds=30.0,
            request_max_retries=2,
            temperature=0.7,
            top_p=0.9,
            top_k=0,
            min_p=0.05,
        ),
        md_gen=MdGenSettings(
            prompts=PromptSettings(summary_prompt_path=None, summary_prompt_text="summary prompt"),
            image=ImageSettings(max_longest_edge_px=1540, token_threshold=16000),
        ),
        md_mrg=MdMrgSettings(
            score=PromptSettings(summary_prompt_path=None, summary_prompt_text="score prompt")
        ),
        runtime=RuntimeSettings(dry_run=False, overwrite=False, verbose=False),
    )


def test_run_chat_writes_raw_response_json(tmp_path: Path, monkeypatch) -> None:
    system_prompt_path = tmp_path / "system.md"
    user_prompt_path = tmp_path / "user.md"
    system_prompt_path.write_text("system", encoding="utf-8")
    user_prompt_path.write_text("user", encoding="utf-8")

    class DummyGateway:
        def __init__(self, endpoint_url: str, model_name: str):
            self.endpoint_url = endpoint_url
            self.model_name = model_name

        def send_text_request(self, request):
            return TextResponse(
                model_name="lang",
                text="answer",
                raw_response={"choices": [{"message": {"content": "answer"}}]},
            )

    monkeypatch.setattr(chat, "LlamaLanguageGateway", DummyGateway)

    output_dir = tmp_path / "out"
    config = _make_config(output_dir=output_dir)

    result = chat.run_chat(config=config, system=system_prompt_path, user=user_prompt_path)

    assert result == 0
    artifact_path = output_dir / "raw_response.json"
    assert artifact_path.exists()
    assert json.loads(artifact_path.read_text(encoding="utf-8")) == {
        "choices": [{"message": {"content": "answer"}}]
    }


def test_run_chat_warns_and_continues_when_raw_response_is_not_serializable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    system_prompt_path = tmp_path / "system.md"
    user_prompt_path = tmp_path / "user.md"
    system_prompt_path.write_text("system", encoding="utf-8")
    user_prompt_path.write_text("user", encoding="utf-8")

    class DummyGateway:
        def __init__(self, endpoint_url: str, model_name: str):
            self.endpoint_url = endpoint_url
            self.model_name = model_name

        def send_text_request(self, request):
            return TextResponse(
                model_name="lang",
                text="answer",
                raw_response={"bad": {1, 2, 3}},
            )

    monkeypatch.setattr(chat, "LlamaLanguageGateway", DummyGateway)

    output_dir = tmp_path / "out"
    config = _make_config(output_dir=output_dir)

    result = chat.run_chat(config=config, system=system_prompt_path, user=user_prompt_path)
    captured = capsys.readouterr()

    assert result == 0
    assert "WARNING failed to persist raw response JSON" in captured.out


def test_run_chat_warns_when_output_dir_not_configured(tmp_path: Path, monkeypatch, capsys) -> None:
    system_prompt_path = tmp_path / "system.md"
    user_prompt_path = tmp_path / "user.md"
    system_prompt_path.write_text("system", encoding="utf-8")
    user_prompt_path.write_text("user", encoding="utf-8")

    class DummyGateway:
        def __init__(self, endpoint_url: str, model_name: str):
            self.endpoint_url = endpoint_url
            self.model_name = model_name

        def send_text_request(self, request):
            return TextResponse(
                model_name="lang",
                text="answer",
                raw_response={"choices": []},
            )

    monkeypatch.setattr(chat, "LlamaLanguageGateway", DummyGateway)

    config = _make_config(output_dir=Path())
    result = chat.run_chat(config=config, system=system_prompt_path, user=user_prompt_path)
    captured = capsys.readouterr()

    assert result == 0
    assert "WARNING raw response not persisted: output directory is not configured" in captured.out
