"""Shared connectors and utilities across modules."""

from .config import (
    AppConfig, 
    build_config_from_args
)

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
    "AppConfig",
    "build_config_from_args",
# ---
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
