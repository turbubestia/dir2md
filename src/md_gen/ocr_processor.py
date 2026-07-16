from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from common.gateway import LlamaOcrGateway

if TYPE_CHECKING:
    from .config import AppConfig


def extract_markdown(config: AppConfig, image: Image.Image) -> str:
    with LlamaOcrGateway(
        endpoint_url=config.ocr_model.endpoint_url,
        model_name=config.ocr_model.model_name,
    ) as gateway:
        response = gateway.send_ocr_request_from_image(image)
    return response.markdown_text