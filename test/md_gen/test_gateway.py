import json
from pathlib import Path

import httpx
from PIL import Image

from common.gateway import (
    GatewayError,
    LlamaOcrGateway,
    TextRequest,
    LlamaLanguageGateway,
)


def _make_image(path: Path) -> None:
    image = Image.new("RGB", (32, 32), color=(255, 255, 255))
    image.save(path)
    image.close()


def test_build_vision_request_payload_matches_openai_vision_shape(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    _make_image(image_path)

    with LlamaOcrGateway(
        endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
    ) as gateway:
        messages = gateway.build_ocr_request_messages(image_path)
        payload = gateway._build_payload(messages)
        assert payload["model"] == "lightonocr-2"
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"][0]["type"] == "image_url"
        assert payload["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")


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
    
    with LlamaOcrGateway (
        endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        client=client,
    ) as gateway:
        response = gateway.send_ocr_request(image_path=image_path)
        assert attempts["count"] == 2
        assert "OCR Output" in response.markdown_text


def test_gateway_maps_timeout_error(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    _make_image(image_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=0.01)

    with LlamaOcrGateway (
        endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        client=client,
    ) as gateway:
        try:
            gateway.send_ocr_request(image_path=image_path)
        except GatewayError as exc:
            assert exc.error_code == "inference_timeout_error"
        else:
            raise AssertionError("Expected GatewayError for timeout")


def test_build_text_summary_payload_uses_system_and_user_messages() -> None:

    with LlamaLanguageGateway(
        endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="qwen3-1.7b",
    ) as gateway:
        request = TextRequest(
            system_prompt="Make a summary of the following text.",
            user_prompt="OCR markdown output",
        )
        messages = gateway.build_text_request_messages(request)
        payload = gateway._build_payload(messages)
        assert payload["model"] == "qwen3-1.7b"
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "OCR markdown output"
        assert payload["temperature"] == 0


def test_language_gateway_keeps_generic_text_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "message": {
                        "content": "Invoice #123\nTotal: $500.00",
                    }
                }
            ]
        }
        return httpx.Response(status_code=200, content=json.dumps(body))

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    with LlamaLanguageGateway(
        endpoint_url="http://localhost:8081/v1/chat/completions",
        model_name="qwen3-1.7b",
        client=client,
    ) as gateway:
        request = TextRequest(system_prompt="Return raw text", user_prompt="Give me an invoice summary")
        response = gateway.send_text_request(request)
        assert response.text == "Invoice #123\nTotal: $500.00"
