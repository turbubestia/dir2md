"""md-gen foundation package."""

from .cli import build_parser
from .discovery import FileItem
from .rasterizer import RasterizationError

__all__ = [
    # discovery and rasterization
    "FileItem",
    "RasterizationError",
    "build_parser",
]
