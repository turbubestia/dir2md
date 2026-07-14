"""md-gen foundation package."""

from common.gateway import GatewayError, LlamaOcrGateway, TextRequest, LlamaLanguageGateway

from .cli import build_parser
from .config import AppConfig, build_config_from_args
from .discovery import FileItem
from .rasterizer import RasterizationError

__all__ = [
    # general configuration
    "AppConfig",
    # gateway related
    "GatewayError",
    "LlamaOcrGateway",
    "TextRequest",
    "LlamaLanguageGateway",
    # discovery and rasterization
    "FileItem",
    "RasterizationError",
    "build_config_from_args",
    "build_parser",
]
