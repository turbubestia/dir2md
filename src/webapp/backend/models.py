"""Pydantic schemas for the webapp settings API.

These models describe the persisted JSON contract in ``data/config/settings.json``
as seen by the webapp. They intentionally mirror the on-disk shape so the
browser UI can load and save the shared configuration file without reshaping it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, NonNegativeInt, PositiveFloat


SourceFileType = Literal["pdf", "image"]
FolderStatusKind = Literal[
    "not_configured",
    "missing",
    "not_directory",
    "inaccessible",
    "empty",
    "ready",
]
WorkflowMessageSeverity = Literal["info", "success", "warning", "error"]


class WorkflowStatusMessage(BaseModel):
    severity: WorkflowMessageSeverity
    code: str
    message: str


class FolderStatus(BaseModel):
    path: str
    status: FolderStatusKind
    message: str
    item_count: int | None = None


class WorkflowSourceFile(BaseModel):
    id: str
    display_name: str
    absolute_path: str
    extension: str
    size_bytes: int
    source_type: SourceFileType
    order_index: int
    preview_url: str | None = None


class WorkflowMetrics(BaseModel):
    pdf_count: int
    image_count: int
    total_count: int


class WorkflowDiscoveryResponse(BaseModel):
    ok: bool
    source_status: FolderStatus
    output_status: FolderStatus
    metrics: WorkflowMetrics
    items: list[WorkflowSourceFile]
    messages: list[WorkflowStatusMessage]


class ModelEndpointSettings(BaseModel):
    """Configuration for an OpenAI-compatible model endpoint."""

    endpoint: AnyHttpUrl = Field(..., description="HTTP(S) endpoint URL.")
    model: str = Field(..., min_length=1, description="Model identifier.")
    timeout_seconds: PositiveFloat = Field(
        ..., description="Request timeout in seconds."
    )
    max_retries: NonNegativeInt = Field(
        ..., description="Maximum retry attempts for failed requests."
    )


class MdGenSummarySettings(BaseModel):
    """md_gen summary prompt configuration."""

    prompt_path: str = Field(..., min_length=1)


class MdGenImageSettings(BaseModel):
    """md_gen image preprocessing configuration."""

    max_longest_edge_px: int = Field(..., ge=1)
    token_threshold: int = Field(..., ge=1)


class MdGenSettings(BaseModel):
    """Top-level md_gen settings section."""

    summary: MdGenSummarySettings
    image: MdGenImageSettings


class MdMrgScoreSettings(BaseModel):
    """md_mrg scoring prompt configuration."""

    prompt_path: str = Field(..., min_length=1)


class MdMrgSettings(BaseModel):
    """Top-level md_mrg settings section."""

    score: MdMrgScoreSettings


class AppSettings(BaseModel):
    """Root settings document returned and accepted by the webapp API.

    ``source_folder`` and ``output_folder`` are intentionally plain strings.
    The webapp does not validate directory existence; that remains the CLI's
    responsibility at runtime.
    """

    app_name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    source_folder: str = Field(
        default="",
        description="Filesystem path to the source folder (text only).",
    )
    output_folder: str = Field(
        default="",
        description="Filesystem path to the output folder (text only).",
    )
    verbose: bool = Field(default=False)
    overwrite: bool = Field(default=False)
    ocr_model: ModelEndpointSettings
    language_model: ModelEndpointSettings
    md_gen: MdGenSettings
    md_mrg: MdMrgSettings
