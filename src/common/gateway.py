from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image

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

# {
#   "id": "chatcmpl-123",
#   "object": "chat.completion",
#   "created": 1677652288,
#   "model": "lightonai/LightOnOCR-2-1B",
#   "choices": [
#     {
#       "index": 0,
#       "message": {
#         "role": "assistant",
#         "content": "# Document Title\n\nThis is the transcribed markdown text extracted by LightOnOCR2 from your image..."
#       },
#       "finish_reason": "stop"
#     }
#   ],
#   "usage": {
#     "prompt_tokens": 1024,
#     "completion_tokens": 256,
#     "total_tokens": 1280
#   }
# }

def _extract_text_content(response_json: dict[str, Any]) -> str:
    # we are asking only one completion, so we only look at the first choice
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GatewayError("invalid_payload_error", "Response missing choices")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    # content should be strictly a string
    if isinstance(content, str):
        return content
   
    raise GatewayError("invalid_payload_error", "Response content format not supported")

# Gateway Interface -----------------------------------------------------------

# This gateway class allows to configure a LLM endpoint and send requests to it, handling retries, timeouts, 
# and payload construction. The post method receives a list of messages that will be embedded in the OpenAI
# chat completion payload.

class _BaseGateway:

    _request_timeout_seconds: float = 120

    request_max_retries: int = 2
    gateway_label: str = "gateway"
    temperature: float = 0.0
    max_tokens: int = 4096
    stream: bool = False

    def __init__( self, endpoint_url: str, model_name: str, client: httpx.Client | None = None, ):
        self._endpoint_url = endpoint_url
        self._model_name = model_name
        self._client = client or httpx.Client(timeout = self._request_timeout_seconds)
        self._owns_client = client is None

    # properties --------------------------------------------------------------

    @property
    def request_timeout_seconds(self) -> float:
        return self._request_timeout_seconds
    
    @request_timeout_seconds.setter
    def request_timeout_seconds(self, value: float) -> None:
        self._request_timeout_seconds = value
        if self._owns_client:
            self._client.timeout = self._request_timeout_seconds

    # context management ------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    # methods -----------------------------------------------------------------

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # private or protected methods --------------------------------------------

    def _build_payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": self._model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": self.stream,
            "messages": messages,
        }

    def _post_with_retry(self, messages: list[dict[str, Any]]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.request_max_retries + 1):
            try:
                payload = self._build_payload(messages)
                response = self._client.post(self._endpoint_url, json=payload)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.request_max_retries:
                    continue
                raise GatewayError("inference_timeout_error", f"{self.gateway_label} request timed out: {exc}") from exc
            except httpx.ConnectError as exc:
                last_error = exc
                if attempt < self.request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Failed to connect to {self.gateway_label} endpoint: {exc}") from exc
            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < self.request_max_retries:
                    continue
                raise GatewayError("connection_error", f"Network error while calling {self.gateway_label} endpoint: {exc}") from exc

            if response.status_code in {503, 502, 429} and attempt < self.request_max_retries:
                continue
            
            self._validate_status(response)

            return response

        raise GatewayError("connection_error", f"{self.gateway_label} request failed after retries: {last_error}")

    def _validate_status(self, response: httpx.Response) -> None:
        label = self.gateway_label.capitalize()
        if response.status_code == 400:
            raise GatewayError("invalid_payload_error", f"{label} gateway rejected payload: {response.text}")
        if response.status_code in {404, 503}:
            raise GatewayError("model_unavailable_error", f"{label} model unavailable: {response.text}")
        if response.status_code >= 500:
            raise GatewayError("model_unavailable_error", f"{label} backend error: {response.text}")
        if response.status_code >= 300:
            raise GatewayError("invalid_payload_error", f"Unexpected {self.gateway_label} response status: {response.status_code}")

# OCR Gateway -----------------------------------------------------------------

# The OCR gateway builds a message that wraps the image data in a base64-encoded payload and 
# constructs a message suitable for the LLM endpoint.

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


class LlamaOcrGateway(_BaseGateway):
    def __init__( self, endpoint_url: str, model_name: str, client: httpx.Client | None = None, ):
        super().__init__( endpoint_url, model_name, client )
        self._gateway_label = "ocr"

    def build_ocr_request_messages(self, image_path: Path) -> list[dict[str, Any]]:
        mime_type = _mime_type_for_path(image_path)
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload =  f"data:{mime_type};base64,{encoded}"
        return [
            { "role": "user", "content": [ { "type": "image_url", "image_url": { "url": payload }, },], }
        ]

    def build_ocr_request_messages_from_image(self, image: Image.Image) -> list[dict[str, Any]]:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        payload = f"data:image/png;base64,{encoded}"
        return [
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": payload}}]}
        ]

    def send_ocr_request(self, image_path: Path) -> OcrResponse:
        messages = self.build_ocr_request_messages(image_path=image_path)
        response = self._post_with_retry(messages)
        response_json = response.json()
        markdown_text = _extract_text_content(response_json)
        return OcrResponse(
            image_path = image_path,
            model_name = self._model_name,
            markdown_text = markdown_text,
            raw_response = response_json,
        )

    def send_ocr_request_from_image(self, image: Image.Image) -> OcrResponse:
        messages = self.build_ocr_request_messages_from_image(image)
        response = self._post_with_retry(messages)
        response_json = response.json()
        markdown_text = _extract_text_content(response_json)
        return OcrResponse(
            image_path=Path("-"),
            model_name=self._model_name,
            markdown_text=markdown_text,
            raw_response=response_json,
        )
    

# Generic Language Gateway ----------------------------------------------------

# The language gateway builds a message sequence from a system prompt and a user prompt, suitable 
# for the LLM endpoint. It is up to the application to build the prompts for the purpose they need.

@dataclass(frozen=True)
class TextRequest:
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class TextResponse:
    model_name: str
    text: str
    raw_response: dict[str, Any]


class LlamaLanguageGateway(_BaseGateway):

    def __init__( self, endpoint_url: str, model_name: str, client: httpx.Client | None = None, ):
        super().__init__( endpoint_url, model_name, client )
        self._gateway_label = "language"

    def build_text_request_messages(self, request: TextRequest) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

    def send_text_request(self, request: TextRequest) -> TextResponse:
        messages = self.build_text_request_messages(request=request)
        response = self._post_with_retry(messages)
        response_json = response.json()
        text = _extract_text_content(response_json)
        return TextResponse(
            model_name = self._model_name,
            text = text,
            raw_response = response_json,
        )



