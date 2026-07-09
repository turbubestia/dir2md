from __future__ import annotations

import base64
import json
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

# error data structures -------------------------------------------------------

GatewayErrorCode = Literal[
    "connection_error",
    "model_unavailable_error",
    "invalid_payload_error",
    "inference_timeout_error",
]

class GatewayError(RuntimeError):
    def __init__(self, error_code: GatewayErrorCode, message: str):
        super().__init__(message)
        self.error_code = error_code

# private helper functions ----------------------------------------------------

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

_SUMMARY_ALLOWED_CHARS = re.compile(r"[^a-zA-Z0-9 .\-_]+")

# Gateway Interface -----------------------------------------------------------

class _BaseGateway:
    def __init__(
        self,
        endpoint_url: str,
        model_name: str,
        request_timeout_seconds: float,
        request_max_retries: int,
        client: httpx.Client | None = None,
        gateway_label: str = "gateway",
    ):
        self._endpoint_url = endpoint_url
        self._model_name = model_name
        self._request_timeout_seconds = request_timeout_seconds
        self._request_max_retries = max(0, request_max_retries)
        self._client = client or httpx.Client(timeout=request_timeout_seconds)
        self._owns_client = client is None
        self._gateway_label = gateway_label

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self):
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
                raise GatewayError("inference_timeout_error", f"{self._gateway_label} request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Failed to connect to {self._gateway_label} endpoint: {exc}") from exc
            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < self._request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Network error while calling {self._gateway_label} endpoint: {exc}") from exc

            if response.status_code in {503, 502, 429} and attempt < self._request_max_retries:
                continue
            return response

        raise GatewayError("connection_error", f"{self._gateway_label} request failed after retries: {last_error}")

    def _validate_status(self, response: httpx.Response) -> None:
        label = self._gateway_label.capitalize()
        if response.status_code == 400:
            raise GatewayError("invalid_payload_error", f"{label} gateway rejected payload: {response.text}")
        if response.status_code in {404, 503}:
            raise GatewayError("model_unavailable_error", f"{label} model unavailable: {response.text}")
        if response.status_code >= 500:
            raise GatewayError("model_unavailable_error", f"{label} backend error: {response.text}")
        if response.status_code >= 300:
            raise GatewayError("invalid_payload_error", f"Unexpected {self._gateway_label} response status: {response.status_code}")

# OCR Gateway -----------------------------------------------------------------

@dataclass(frozen=True)
class OcrRequest:
    image_path: Path
    prompt_text: str

def build_default_ocr_requests(image_paths: tuple[Path, ...]) -> tuple[OcrRequest, ...]:
    prompt = "Extract the full document content as markdown. Preserve structure and tables when possible."
    return tuple(OcrRequest(image_path=image_path, prompt_text=prompt) for image_path in image_paths)


@dataclass(frozen=True)
class OcrResponse:
    image_path: Path
    model_name: str
    markdown_text: str
    raw_response: dict[str, Any]

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
                    {
                        "type": "image_url",
                        "image_url": {"url": _build_data_url(request.image_path)},
                    },
                ],
            }
        ],
        "temperature": 0,
    }

class LlamaOcrGateway(_BaseGateway):
    def __init__(
        self,
        endpoint_url: str,
        model_name: str,
        request_timeout_seconds: float,
        request_max_retries: int,
        client: httpx.Client | None = None,
    ):
        super().__init__(
            endpoint_url=endpoint_url,
            model_name=model_name,
            request_timeout_seconds=request_timeout_seconds,
            request_max_retries=request_max_retries,
            client=client,
            gateway_label="ocr",
        )

    def send_ocr_request(self, request: OcrRequest) -> OcrResponse:
        payload = build_vision_request_payload(model_name=self._model_name, request=request)
        response = self._post_with_retry(payload)
        self._validate_status(response)

        response_json = response.json()
        markdown_text = _extract_text_content(response_json)
        return OcrResponse(
            image_path=request.image_path,
            model_name=self._model_name,
            markdown_text=markdown_text,
            raw_response=response_json,
        )

    def send_ocr_requests(self, requests: tuple[OcrRequest, ...]) -> tuple[OcrResponse, ...]:
        return tuple(self.send_ocr_request(request) for request in requests)

# Generic Language Gateway ----------------------------------------------------

@dataclass(frozen=True)
class TextRequest:
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class TextResponse:
    model_name: str
    text: str
    raw_response: dict[str, Any]

def build_text_request_payload(model_name: str, request: TextRequest) -> dict[str, Any]:
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ],
        "temperature": 0,
    }

class LlamaLanguageGateway(_BaseGateway):
    def __init__(
        self,
        endpoint_url: str,
        model_name: str,
        request_timeout_seconds: float,
        request_max_retries: int,
        client: httpx.Client | None = None,
    ):
        super().__init__(
            endpoint_url=endpoint_url,
            model_name=model_name,
            request_timeout_seconds=request_timeout_seconds,
            request_max_retries=request_max_retries,
            client=client,
            gateway_label="language",
        )

    def send_text_request(self, request: TextRequest) -> TextResponse:
        payload = build_text_request_payload(model_name=self._model_name, request=request)
        response = self._post_with_retry(payload)
        self._validate_status(response)

        response_json = response.json()
        text = _extract_text_content(response_json)
        return TextResponse(
            model_name=self._model_name,
            text=text,
            raw_response=response_json,
        )

# Summary Specialization Gateway ----------------------------------------------

@dataclass(frozen=True)
class SummaryRequest:
    source_text: str


@dataclass(frozen=True)
class SummaryResponse:
    source_text: str
    model_name: str
    summary_text: str
    raw_response: dict[str, Any]

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

def sanitize_summary_text(summary_text: str) -> str:
    normalized = summary_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    cleaned = _SUMMARY_ALLOWED_CHARS.sub(" ", normalized)
    return " ".join(cleaned.split())

class LlamaSummaryGateway(LlamaLanguageGateway):

    def send_summary_request(self, request: SummaryRequest) -> SummaryResponse:
        payload = build_text_summary_request_payload(model_name=self._model_name, request=request)
        response = self._post_with_retry(payload)
        self._validate_status(response)

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

# Page Bridge Score Specialization Gateway ------------------------------------

@dataclass(frozen=True)
class BridgeScoreRequest:
    page_a_end: str
    page_a_summary: str
    page_b_start: str
    page_b_summary: str


@dataclass(frozen=True)
class BridgeScoreResponse:
    model_name: str
    reason: str
    bridge_score: int
    raw_response: dict[str, Any]

def build_bridge_score_request_payload(model_name: str, request: BridgeScoreRequest) -> dict[str, Any]:
    system_prompt = (
        "You are an expert document reconstruction engineer. Review the end of Page A and the start of Page B "
        "along with their summaries. Rate how naturally, grammatically, or contextually Page B continues Page A "
        "on a scale from 0 to 10.\n\n"
        "Scoring Rules:\n"
        "10 = Perfect grammatical fit.\n"
        "7 = Paragraph split or figure/table insertion continuity.\n"
        "5 = Minimum continuity.\n"
        "4 = Similar content but likely different document.\n"
        "3 = Major topic pivot or disjointed vocabulary.\n"
        "0 = Totally unrelated pages.\n\n"
        "Output raw JSON matching this schema exactly: {\"reason\": \"string\", \"bridge_score\": integer}"
    )
    user_prompt = (
        f"Page A End: \"{request.page_a_end}\"\n"
        f"Page A Summary: \"{request.page_a_summary}\"\n"
        f"Page B Start: \"{request.page_b_start}\"\n"
        f"Page B Summary: \"{request.page_b_summary}\""
    )
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }

class LlamaBridgeScoreGateway(LlamaLanguageGateway):

    def send_bridge_score_request(self, request: BridgeScoreRequest) -> BridgeScoreResponse:
        payload = build_bridge_score_request_payload(model_name=self._model_name, request=request)
        response = self._post_with_retry(payload)
        self._validate_status(response)

        response_json = response.json()
        content = _extract_text_content(response_json)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise GatewayError("invalid_payload_error", f"Bridge score response is not valid JSON: {content}") from exc

        reason = parsed.get("reason")
        bridge_score = parsed.get("bridge_score")
        if not isinstance(reason, str) or not isinstance(bridge_score, int):
            raise GatewayError("invalid_payload_error", f"Bridge score payload missing required keys: {parsed}")

        bridge_score = max(0, min(10, bridge_score))
        return BridgeScoreResponse(
            model_name=self._model_name,
            reason=reason,
            bridge_score=bridge_score,
            raw_response=response_json,
        )

