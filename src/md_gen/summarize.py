from __future__ import annotations


from common.gateway import LlamaLanguageGateway, TextRequest
from common.config import AppConfig


def summarize_page(config: AppConfig, page_markdown: str) -> str:
    if not page_markdown.strip():
        return ""
    with LlamaLanguageGateway(
        endpoint_url=config.language_model.endpoint_url,
        model_name=config.language_model.model_name,
    ) as gateway:
        response = gateway.send_text_request(
            TextRequest(
                system_prompt=config.md_gen.prompts.system_text,
                user_prompt=page_markdown,
                assistant_prompt=config.md_gen.prompts.assistant_text,
            )
        )
    return response.text


def summarize_document(config: AppConfig, page_summaries: list[str]) -> str:
    cleaned = [s for s in page_summaries if s.strip()]
    if len(cleaned) == 0:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    combined = "\n\n".join(cleaned)
    return summarize_page(config, combined)
