import json
from pathlib import Path

import httpx
from PIL import Image

from md_gen.gateway import (
    GatewayError,
    LlamaOcrGateway,
    LlamaSummaryGateway,
    OcrRequest,
    SummaryRequest,
    build_text_summary_request_payload,
    build_vision_request_payload,
    sanitize_summary_text,
)


def _make_image(path: Path) -> None:
    image = Image.new("RGB", (32, 32), color=(255, 255, 255))
    image.save(path)
    image.close()


def test_build_vision_request_payload_matches_openai_vision_shape(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    _make_image(image_path)

    payload = build_vision_request_payload(
        model_name="lightonocr-2",
        request=OcrRequest(image_path=image_path, prompt_text="Extract markdown"),
    )

    assert payload["model"] == "lightonocr-2"
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"][0]["type"] == "text"
    assert payload["messages"][0]["content"][1]["type"] == "image_url"
    assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_gateway_retries_and_succeeds_after_transient_unavailable(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    _make_image(image_path)
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(status_code=503, json={"error": "warming up"})
        body = {
            "choices": [
                {
                    "message": {
                        "content": "# OCR Output\n\nHello",
                    }
                }
            ]
        }
        return httpx.Response(status_code=200, content=json.dumps(body))

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    gateway = LlamaOcrGateway(
        endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        request_timeout_seconds=2.0,
        request_max_retries=2,
        client=client,
    )

    response = gateway.send_ocr_request(OcrRequest(image_path=image_path, prompt_text="Extract markdown"))

    assert attempts["count"] == 2
    assert "OCR Output" in response.markdown_text
    client.close()


def test_gateway_maps_timeout_error(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    _make_image(image_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=0.01)
    gateway = LlamaOcrGateway(
        endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        request_timeout_seconds=0.01,
        request_max_retries=0,
        client=client,
    )

    try:
        gateway.send_ocr_request(OcrRequest(image_path=image_path, prompt_text="Extract markdown"))
    except GatewayError as exc:
        assert exc.error_code == "inference_timeout_error"
    else:
        raise AssertionError("Expected GatewayError for timeout")
    client.close()


def test_build_text_summary_payload_uses_system_and_user_messages() -> None:
    payload = build_text_summary_request_payload(
        model_name="qwen3-1.7b",
        request=SummaryRequest(source_text="OCR markdown output"),
    )

    assert payload["model"] == "qwen3-1.7b"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "OCR markdown output"
    assert payload["temperature"] == 0


def test_summary_gateway_parses_and_sanitizes_plain_text_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "message": {
                        "content": "Invoice #123\nTotal: $500.00 <think>ignore</think>",
                    }
                }
            ]
        }
        return httpx.Response(status_code=200, content=json.dumps(body))

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    gateway = LlamaSummaryGateway(
        endpoint_url="http://localhost:8081/v1/chat/completions",
        model_name="qwen3-1.7b",
        request_timeout_seconds=2.0,
        request_max_retries=0,
        client=client,
    )

    response = gateway.send_summary_request(SummaryRequest(source_text="sample"))

    assert response.summary_text == "Invoice 123 Total 500.00 think ignore think"
    client.close()


def test_sanitize_summary_text_keeps_only_plain_ascii_text() -> None:
    assert sanitize_summary_text("A_B:C\nZ@1-2.") == "A B C Z 1-2."
