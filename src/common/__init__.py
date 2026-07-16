"""Shared connectors and utilities across modules."""

# Common errors and exceptions
from .gateway import (
    GatewayError, 
    GatewayErrorCode
)

# OCR Gateway
from .gateway import (
    OcrResponse,
    LlamaOcrGateway,
)

# Language Gateway
from .gateway import (
    TextRequest,
    TextResponse,
    LlamaLanguageGateway,
)

__all__ = [
    "GatewayError",
    "GatewayErrorCode",
# ---
    "LlamaOcrGateway",
    "OcrResponse",
# ---
    "LlamaLanguageGateway",
    "TextRequest",
    "TextResponse",
]
