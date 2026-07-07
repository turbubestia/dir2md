"""md-gen foundation package."""

from .config import AppConfig, build_config_from_args
from .gateway import GatewayError, LlamaOcrGateway, OcrRequest, OcrResponse, build_vision_request_payload
from .markdown_writer import PersistedMarkdownRecord
from .rasterizer import PdfPageRaster, PdfRasterizationError
from .resizer import ImageResizeResult
from .token_budget import ImageTokenBudgetReport, TokenBudgetValidationError, calculate_vision_tokens

__all__ = [
	"AppConfig",
	"GatewayError",
	"LlamaOcrGateway",
	"OcrRequest",
	"OcrResponse",
	"PersistedMarkdownRecord",
	"PdfPageRaster",
	"PdfRasterizationError",
	"ImageResizeResult",
	"ImageTokenBudgetReport",
	"TokenBudgetValidationError",
	"build_vision_request_payload",
	"calculate_vision_tokens",
	"build_config_from_args",
]
