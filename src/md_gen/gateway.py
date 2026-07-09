"""Compatibility shim for shared llama gateway connectors.

The canonical implementation now lives in `common.llama_gateway` so both
`md_gen` and `md_mrg` can reuse the same transport behavior.
"""

from common.llama_gateway import (
    BridgeScoreRequest,
    BridgeScoreResponse,
    GatewayError,
    GatewayErrorCode,
    LlamaBridgeScoreGateway,
    LlamaLanguageGateway,
    LlamaOcrGateway,
    LlamaSummaryGateway,
    OcrRequest,
    OcrResponse,
    SummaryRequest,
    SummaryResponse,
    TextRequest,
    TextResponse,
    build_bridge_score_request_payload,
    build_default_ocr_requests,
    build_text_request_payload,
    build_text_summary_request_payload,
    build_vision_request_payload,
    sanitize_summary_text,
)

__all__ = [
    "BridgeScoreRequest",
    "BridgeScoreResponse",
    "GatewayError",
    "GatewayErrorCode",
    "LlamaBridgeScoreGateway",
    "LlamaLanguageGateway",
    "LlamaOcrGateway",
    "LlamaSummaryGateway",
    "OcrRequest",
    "OcrResponse",
    "SummaryRequest",
    "SummaryResponse",
    "TextRequest",
    "TextResponse",
    "build_bridge_score_request_payload",
    "build_default_ocr_requests",
    "build_text_request_payload",
    "build_text_summary_request_payload",
    "build_vision_request_payload",
    "sanitize_summary_text",
]
