"""Shared connectors and utilities across modules."""

# Common errors and exceptions
from .llama_gateway import (
    GatewayError, 
    GatewayErrorCode
)

# OCR Gateway
from .llama_gateway import (
    OcrRequest,
    OcrResponse,
    LlamaOcrGateway,
    build_default_ocr_requests,
    build_vision_request_payload,
)

# Language Gateway
from .llama_gateway import (
    TextRequest,
    TextResponse,
    LlamaLanguageGateway,
    build_text_request_payload,
)

# Summary Gateway
from .llama_gateway import (
    SummaryRequest,
    SummaryResponse,
    build_text_summary_request_payload,
    sanitize_summary_text,
)

# Bridge Score Gateway
from .llama_gateway import (
    BridgeScoreRequest,
    BridgeScoreResponse,
    build_bridge_score_request_payload,
)

__all__ = [
    "GatewayError",
    "GatewayErrorCode",
# ---
    "LlamaOcrGateway",
    "OcrRequest",
    "OcrResponse",
    "build_default_ocr_requests",
    "build_vision_request_payload",
# ---
    "LlamaLanguageGateway",
    "TextRequest",
    "TextResponse",
    "build_text_request_payload",
# ---
    "SummaryRequest",
    "SummaryResponse",
    "build_text_summary_request_payload",
    "sanitize_summary_text",
# ---
    "BridgeScoreRequest",
    "BridgeScoreResponse",
    "build_bridge_score_request_payload",
]
