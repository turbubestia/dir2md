from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

GatewayErrorCode = Literal[
    "connection_error",
    "model_unavailable_error",
    "invalid_payload_error",
    "inference_timeout_error",
]


@dataclass(frozen=True)
class OcrRequest:
    image_path: Path
    prompt_text: str


@dataclass(frozen=True)
class OcrResponse:
    image_path: Path
    model_name: str
    markdown_text: str
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class SummaryRequest:
    source_text: str


@dataclass(frozen=True)
class SummaryResponse:
    source_text: str
    model_name: str
    summary_text: str
    raw_response: dict[str, Any]


class GatewayError(RuntimeError):
    def __init__(self, error_code: GatewayErrorCode, message: str):
        super().__init__(message)
        self.error_code = error_code


def _mime_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix in {".tif", ".tiff"}:
        return "image/tiff"
    if suffix == ".bmp":
        return "image/bmp"
    return "image/png"


def _build_data_url(image_path: Path) -> str:
    mime_type = _mime_type_for_path(image_path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_vision_request_payload(model_name: str, request: OcrRequest) -> dict[str, Any]:
    return {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": _build_data_url(request.image_path)},
                    },
                ],
            }
        ],
        "temperature": 0,
    }


def build_text_summary_request_payload(model_name: str, request: SummaryRequest) -> dict[str, Any]:
    system_prompt = (
        "You are an automated data-extraction parser. You process OCR text and output a concise summary "
        "no longer than three lines.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- DO NOT use thinking tags (<think>...</think>).\n"
        "- DO NOT output chain-of-thought reasoning, explanations, or introductory text.\n"
        "- Return only plain text summary content.\n"
        "- Avoid markdown formatting."
    )
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.source_text},
        ],
        "temperature": 0,
    }


_SUMMARY_ALLOWED_CHARS = re.compile(r"[^a-zA-Z0-9 .\-]+")


def sanitize_summary_text(summary_text: str) -> str:
    normalized = summary_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    cleaned = _SUMMARY_ALLOWED_CHARS.sub(" ", normalized)
    return " ".join(cleaned.split())


def _extract_markdown_text(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GatewayError("invalid_payload_error", "OCR response missing choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        return "\n".join(part for part in text_parts if part)
    raise GatewayError("invalid_payload_error", "OCR response content format not supported")


def _extract_text_content(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GatewayError("invalid_payload_error", "Response missing choices")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        return "\n".join(part for part in text_parts if part)
    raise GatewayError("invalid_payload_error", "Response content format not supported")


class LlamaOcrGateway:
    def __init__(
        self,
        endpoint_url: str,
        model_name: str,
        request_timeout_seconds: float,
        request_max_retries: int,
        client: httpx.Client | None = None,
    ):
        self._endpoint_url = endpoint_url
        self._model_name = model_name
        self._request_timeout_seconds = request_timeout_seconds
        self._request_max_retries = max(0, request_max_retries)
        self._client = client or httpx.Client(timeout=request_timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "LlamaOcrGateway":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _post_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._request_max_retries + 1):
            try:
                response = self._client.post(self._endpoint_url, json=payload)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("inference_timeout_error", f"OCR request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Failed to connect to OCR endpoint: {exc}") from exc
            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Network error while calling OCR endpoint: {exc}") from exc

            if response.status_code in {503, 502, 429} and attempt < self._request_max_retries:
                continue
            return response

        raise GatewayError("connection_error", f"OCR request failed after retries: {last_error}")

    def send_ocr_request(self, request: OcrRequest) -> OcrResponse:
        payload = build_vision_request_payload(model_name=self._model_name, request=request)
        response = self._post_with_retry(payload)

        if response.status_code == 400:
            raise GatewayError("invalid_payload_error", f"OCR gateway rejected payload: {response.text}")
        if response.status_code in {404, 503}:
            raise GatewayError("model_unavailable_error", f"OCR model unavailable: {response.text}")
        if response.status_code >= 500:
            raise GatewayError("model_unavailable_error", f"OCR backend error: {response.text}")
        if response.status_code >= 300:
            raise GatewayError("invalid_payload_error", f"Unexpected OCR response status: {response.status_code}")

        response_json = response.json()
        markdown_text = _extract_markdown_text(response_json)
        return OcrResponse(
            image_path=request.image_path,
            model_name=self._model_name,
            markdown_text=markdown_text,
            raw_response=response_json,
        )

    def send_ocr_requests(self, requests: tuple[OcrRequest, ...]) -> tuple[OcrResponse, ...]:
        return tuple(self.send_ocr_request(request) for request in requests)


class LlamaSummaryGateway:
    def __init__(
        self,
        endpoint_url: str,
        model_name: str,
        request_timeout_seconds: float,
        request_max_retries: int,
        client: httpx.Client | None = None,
    ):
        self._endpoint_url = endpoint_url
        self._model_name = model_name
        self._request_timeout_seconds = request_timeout_seconds
        self._request_max_retries = max(0, request_max_retries)
        self._client = client or httpx.Client(timeout=request_timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "LlamaSummaryGateway":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _post_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._request_max_retries + 1):
            try:
                response = self._client.post(self._endpoint_url, json=payload)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("inference_timeout_error", f"Summary request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Failed to connect to summary endpoint: {exc}") from exc
            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Network error while calling summary endpoint: {exc}") from exc

            if response.status_code in {503, 502, 429} and attempt < self._request_max_retries:
                continue
            return response

        raise GatewayError("connection_error", f"Summary request failed after retries: {last_error}")

    def send_summary_request(self, request: SummaryRequest) -> SummaryResponse:
        payload = build_text_summary_request_payload(model_name=self._model_name, request=request)
        response = self._post_with_retry(payload)

        if response.status_code == 400:
            raise GatewayError("invalid_payload_error", f"Summary gateway rejected payload: {response.text}")
        if response.status_code in {404, 503}:
            raise GatewayError("model_unavailable_error", f"Summary model unavailable: {response.text}")
        if response.status_code >= 500:
            raise GatewayError("model_unavailable_error", f"Summary backend error: {response.text}")
        if response.status_code >= 300:
            raise GatewayError("invalid_payload_error", f"Unexpected summary response status: {response.status_code}")

        response_json = response.json()
        summary_text = sanitize_summary_text(_extract_text_content(response_json))
        return SummaryResponse(
            source_text=request.source_text,
            model_name=self._model_name,
            summary_text=summary_text,
            raw_response=response_json,
        )

    def send_summary_requests(self, requests: tuple[SummaryRequest, ...]) -> tuple[SummaryResponse, ...]:
        return tuple(self.send_summary_request(request) for request in requests)


def build_default_ocr_requests(image_paths: tuple[Path, ...]) -> tuple[OcrRequest, ...]:
    prompt = "Extract the full document content as markdown. Preserve structure and tables when possible."
    return tuple(OcrRequest(image_path=image_path, prompt_text=prompt) for image_path in image_paths)