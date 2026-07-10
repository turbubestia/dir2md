from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from common.llama_gateway import LlamaLanguageGateway, TextRequest

from .io import derive_image_dir, derive_markdown_dir, derive_plan_file, validate_merge_batch_payload


_LETTER_RATIO = 8.5 / 11.0
_LEGAL_RATIO = 8.5 / 14.0
_DPI = 300
_LETTER_SIZE = (int(8.5 * _DPI), int(11 * _DPI))
_LEGAL_SIZE = (int(8.5 * _DPI), int(14 * _DPI))
_FILENAME_RE = re.compile(r"[^a-z0-9]+")


class ApplyError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def _sanitize_component(value: str) -> str:
    normalized = _FILENAME_RE.sub("-", value.lower()).strip("-")
    return normalized or "document"


def _extract_llm_filename_stem(text: str) -> str:
    candidate_line = ""
    for raw_line in text.splitlines():
        cleaned = raw_line.strip()
        if cleaned:
            candidate_line = cleaned
            break
    if not candidate_line:
        candidate_line = text.strip()
    candidate_line = candidate_line.split(":", 1)[-1].strip()
    candidate_line = candidate_line.replace("/", "-")
    return _sanitize_component(candidate_line)


def _choose_canvas_size(image_size: tuple[int, int]) -> tuple[int, int]:
    width, height = image_size
    ratio = width / height if height else 1.0
    if abs(ratio - _LETTER_RATIO) <= 0.06:
        return _LETTER_SIZE
    if abs(ratio - _LEGAL_RATIO) <= 0.06:
        return _LEGAL_SIZE
    return _LETTER_SIZE


def _fit_image_to_canvas(image: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", canvas_size, color=(255, 255, 255))
    source = image.convert("RGB")
    source.thumbnail(canvas_size, Image.Resampling.LANCZOS)
    x_offset = (canvas_size[0] - source.width) // 2
    y_offset = (canvas_size[1] - source.height) // 2
    canvas.paste(source, (x_offset, y_offset))
    source.close()
    return canvas


def _build_pdf_from_images(image_paths: tuple[Path, ...], output_pdf: Path) -> None:
    if not image_paths:
        return

    page_images: list[Image.Image] = []
    for image_path in image_paths:
        with Image.open(image_path) as source_image:
            canvas_size = _choose_canvas_size(source_image.size)
            page_images.append(_fit_image_to_canvas(source_image, canvas_size))

    first_page, *rest_pages = page_images
    first_page.save(
        output_pdf,
        format="PDF",
        save_all=True,
        append_images=rest_pages,
        resolution=_DPI,
    )
    for page_image in page_images:
        page_image.close()


def _merge_fragment_snippets(document: dict[str, Any]) -> str:
    fragments = document.get("fragments", [])
    snippets: list[str] = []
    if isinstance(fragments, list):
        for fragment in fragments:
            if not isinstance(fragment, dict):
                continue
            content = fragment.get("content_fingerprint")
            if isinstance(content, dict):
                snippet = str(content.get("snippet", "")).strip()
                if snippet:
                    snippets.append(snippet)
    return " ".join(snippets).strip()


def _propose_document_stem(
    document: dict[str, Any],
    naming_endpoint_url: str | None,
    naming_model_name: str | None,
    naming_timeout_seconds: float,
    naming_max_retries: int,
) -> str:
    source_name = str(document.get("source_name", "document"))
    merged_snippet = _merge_fragment_snippets(document)
    source_identifier = str(document.get("source_name", "document"))
    base_prompt = (
        "Propose a short filesystem-safe filename stem using the format date-subject-title. "
        "Use only lowercase letters, numbers, and hyphens. Include identifying cues such as dates, "
        "medical/utility/service topics, invoice or account references, and the shortest distinct title possible."
    )
    user_prompt = (
        f"Source name: {source_name}\n"
        f"Document identifier hints: {source_identifier}\n"
        f"Merged summary: {merged_snippet}\n"
        "Return only the filename stem in the form date-subject-title."
    )

    if naming_endpoint_url and naming_model_name:
        try:
            with LlamaLanguageGateway(
                endpoint_url=naming_endpoint_url,
                model_name=naming_model_name,
                request_timeout_seconds=naming_timeout_seconds,
                request_max_retries=naming_max_retries,
            ) as gateway:
                response = gateway.send_text_request(TextRequest(system_prompt=base_prompt, user_prompt=user_prompt))
                candidate = _extract_llm_filename_stem(response.text)
                if candidate:
                    return candidate
        except Exception:
            pass

    return _sanitize_component(f"{source_name}-{merged_snippet[:48]}")


def apply_merge_plan(
    source_root: Path,
    naming_endpoint_url: str | None = "http://localhost:8081/v1/chat/completions",
    naming_model_name: str | None = "qwen3-1.7b",
    naming_timeout_seconds: float = 30.0,
    naming_max_retries: int = 0,
    overwrite: bool = False,
) -> int:
    source_root = source_root.expanduser().resolve()
    plan_file = derive_plan_file(source_root)
    markdown_dir = derive_markdown_dir(source_root)
    image_dir = derive_image_dir(source_root)

    print(f"APPLY source={source_root}")
    print(f"APPLY plan_file={plan_file}")
    print(f"APPLY markdown_dir={markdown_dir}")
    print(f"APPLY image_dir={image_dir}")

    if not plan_file.exists():
        raise ApplyError("plan_file_not_found", f"Merge plan file not found: {plan_file}")
    if not markdown_dir.exists() or not markdown_dir.is_dir():
        raise ApplyError("markdown_temp_missing", f"Markdown temp directory not found: {markdown_dir}")
    if not image_dir.exists() or not image_dir.is_dir():
        raise ApplyError("image_temp_missing", f"Image temp directory not found: {image_dir}")

    payload = json.loads(plan_file.read_text(encoding="utf-8"))
    validate_merge_batch_payload(payload)
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ApplyError("invalid_merge_batch", "Merge batch is missing documents array")

    output_dir = source_root
    output_dir.mkdir(parents=True, exist_ok=True)

    for document in documents:
        if not isinstance(document, dict):
            continue
        stem = _propose_document_stem(
            document=document,
            naming_endpoint_url=naming_endpoint_url,
            naming_model_name=naming_model_name,
            naming_timeout_seconds=naming_timeout_seconds,
            naming_max_retries=naming_max_retries,
        )
        markdown_output = output_dir / f"{stem}.md"
        pdf_output = output_dir / f"{stem}.pdf"
        if markdown_output.exists() and not overwrite:
            print(f"> skipping file {markdown_output}: already exist")
            continue

        fragments = document.get("fragments")
        if not isinstance(fragments, list):
            continue

        markdown_parts: list[str] = []
        for index, fragment in enumerate(fragments):
            if not isinstance(fragment, dict):
                continue
            markdown_file = fragment.get("markdown_file")
            if not isinstance(markdown_file, str):
                continue
            markdown_path = markdown_dir / markdown_file
            if not markdown_path.exists():
                continue
            markdown_text = markdown_path.read_text(encoding="utf-8")
            markdown_parts.append(markdown_text)
            if index < len(fragments) - 1:
                markdown_parts.append("\n\n---\n\n")

        if not markdown_parts:
            continue

        markdown_output.write_text("".join(markdown_parts).rstrip() + "\n", encoding="utf-8")
        print(f"> wrote merged markdown {markdown_output}")

        image_paths: list[Path] = []
        for fragment in fragments:
            if not isinstance(fragment, dict):
                continue
            image_file = fragment.get("image_file")
            if not isinstance(image_file, str):
                continue
            image_path = image_dir / image_file
            if image_path.exists():
                image_paths.append(image_path)

        if image_paths:
            if pdf_output.exists() and not overwrite:
                print(f"> skipping file {pdf_output}: already exist")
            else:
                _build_pdf_from_images(tuple(image_paths), pdf_output)
                print(f"> wrote merged pdf {pdf_output}")

    return 0
