import json
from pathlib import Path

import httpx
from PIL import Image

from common.llama_gateway import (
    BridgeScoreRequest,
    GatewayError,
    LlamaBridgeScoreGateway,
    LlamaLanguageGateway,
    LlamaOcrGateway,
    LlamaSummaryGateway,
    OcrRequest,
    SummaryRequest,
    TextRequest,
    build_bridge_score_request_payload,
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


def test_build_text_summary_payload_allows_custom_system_prompt() -> None:
    payload = build_text_summary_request_payload(
        model_name="qwen3-1.7b",
        request=SummaryRequest(source_text="OCR markdown output", system_prompt="custom prompt"),
    )

    assert payload["messages"][0]["content"] == "custom prompt"


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
    assert sanitize_summary_text("A_B:C\nZ@1-2.") == "A_B C Z 1-2."


def test_build_bridge_score_payload_has_expected_shape() -> None:
    payload = build_bridge_score_request_payload(
        model_name="qwen3-1.7b",
        request=BridgeScoreRequest(
            page_a_end="total amount due is",
            page_a_summary="utility invoice",
            page_b_start="100.00 payable",
            page_b_summary="same utility invoice details",
        ),
    )

    assert payload["model"] == "qwen3-1.7b"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert "Page A End" in payload["messages"][1]["content"]


def test_language_gateway_parses_bridge_score_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "message": {
                        "content": '{"reason":"natural continuation","bridge_score":8}',
                    }
                }
            ]
        }
        return httpx.Response(status_code=200, content=json.dumps(body))

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    gateway = LlamaBridgeScoreGateway(
        endpoint_url="http://localhost:8081/v1/chat/completions",
        model_name="qwen3-1.7b",
        request_timeout_seconds=2.0,
        request_max_retries=0,
        client=client,
    )

    response = gateway.send_bridge_score_request(
        BridgeScoreRequest(
            page_a_end="total amount due is",
            page_a_summary="utility invoice",
            page_b_start="100.00 payable",
            page_b_summary="same utility invoice details",
        )
    )

    assert response.bridge_score == 8
    assert response.reason == "natural continuation"
    client.close()


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
    gateway = LlamaLanguageGateway(
        endpoint_url="http://localhost:8081/v1/chat/completions",
        model_name="qwen3-1.7b",
        request_timeout_seconds=2.0,
        request_max_retries=0,
        client=client,
    )

    response = gateway.send_text_request(
        TextRequest(system_prompt="Return raw text", user_prompt="Give me an invoice summary")
    )

    assert response.text == "Invoice #123\nTotal: $500.00"
    client.close()
