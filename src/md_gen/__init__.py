"""md-gen foundation package."""

from common.gateway import GatewayError, LlamaOcrGateway, TextRequest, LlamaLanguageGateway

from .cli import build_parser
from .config import AppConfig, build_config_from_args
from .rasterizer import PdfPageRaster, PdfRasterizationError
from .resizer import ImageResizeResult

# from .markdown_writer import PersistedMarkdownRecord

__all__ = [
    # general configuration
	"AppConfig",
    # gateway related
	"GatewayError",
	"LlamaOcrGateway",
    "TextRequest",
	"LlamaLanguageGateway",
    #  rasterization related
	"PdfPageRaster",
	"PdfRasterizationError",
	"ImageResizeResult",
	"build_config_from_args",
	"build_parser",
]
