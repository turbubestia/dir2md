"""Pydantic schemas for the webapp settings API.

These models describe the persisted JSON contract in ``data/config/settings.json``
as seen by the webapp. They intentionally mirror the on-disk shape so the
browser UI can load and save the shared configuration file without reshaping it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, NonNegativeInt, PositiveFloat, model_validator


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
WorkflowStageStatus = Literal["idle", "enabled", "running", "complete", "failed"]
MergeItemStatus = Literal["pending", "running", "done", "failed"]


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


class WorkflowActiveItem(BaseModel):
    source_id: str | None = None
    display_name: str | None = None
    source_type: SourceFileType | None = None
    page_number: int | None = None
    markdown_file: str | None = None


class WorkflowActiveComparison(BaseModel):
    left_source_id: str | None = None
    right_source_id: str | None = None
    left_display_name: str | None = None
    right_display_name: str | None = None


class WorkflowCounts(BaseModel):
    markdown_count: int = 0
    pdf_document_count: int = 0
    image_group_count: int = 0


class WorkflowProgress(BaseModel):
    stage: Literal["idle", "ocr", "planning", "merge"] = "idle"
    total_jobs: int = 0
    completed_jobs: int = 0
    percent: float = 0.0


class WorkflowMergeItem(BaseModel):
    id: str
    label: str
    item_type: Literal["pdf", "group"]
    item_index: int
    status: MergeItemStatus = "pending"
    output_pdf: str | None = None
    output_markdown: str | None = None
    error_code: str | None = None
    message: str | None = None


class WorkflowState(BaseModel):
    discovery: WorkflowDiscoveryResponse | None = None
    ocr_status: WorkflowStageStatus = "idle"
    merge_status: WorkflowStageStatus = "idle"
    llm_test_status: WorkflowStageStatus = "idle"
    llm_test_result: LlmTestResult | None = None
    progress: WorkflowProgress = Field(default_factory=WorkflowProgress)
    counts: WorkflowCounts = Field(default_factory=WorkflowCounts)
    current_item: WorkflowActiveItem | None = None
    active_comparison: WorkflowActiveComparison | None = None
    completed_item_ids: list[str] = Field(default_factory=list)
    active_merge_item_id: str | None = None
    merge_items: list[WorkflowMergeItem] = Field(default_factory=list)
    merge_results_available: bool = False
    merge_result_error: WorkflowStatusMessage | None = None
    messages: list[WorkflowStatusMessage] = Field(default_factory=list)
    error: WorkflowStatusMessage | None = None


class EditablePlanDocumentBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    source_file_name: str = Field(..., min_length=1)
    file_type: SourceFileType
    markdown_file: str = Field(..., min_length=1)
    page_count: int | None = None
    date_of_process: str | None = None
    summary: str | None = None
    status: str | None = None


class EditableImagePage(EditablePlanDocumentBase):
    kind: Literal["image_page"] = "image_page"
    file_type: Literal["image"] = "image"


class EditablePdfDocument(EditablePlanDocumentBase):
    kind: Literal["pdf"] = "pdf"
    file_type: Literal["pdf"] = "pdf"


class EditableImageGroup(BaseModel):
    id: str = Field(..., min_length=1)
    kind: Literal["image_group"] = "image_group"
    display_name: str = Field(..., min_length=1)
    documents: list[EditableImagePage] = Field(..., min_length=1)


EditablePlanItem = EditableImageGroup | EditablePdfDocument


class EditableMergePlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[EditablePlanItem]

    @model_validator(mode="after")
    def reject_duplicate_document_ids(self) -> "EditableMergePlan":
        seen: set[str] = set()
        for item in self.items:
            documents = item.documents if isinstance(item, EditableImageGroup) else [item]
            for document in documents:
                if document.id in seen:
                    raise ValueError(f"Duplicate editable plan document id: {document.id}")
                seen.add(document.id)
        return self


class WorkflowMergeRequest(BaseModel):
    plan: EditableMergePlan


class WorkflowMergeResultItem(BaseModel):
    id: str
    item_index: int
    item_type: Literal["pdf", "group"]
    status: Literal["ok", "failed"]
    label: str
    output_pdf: str | None = None
    output_markdown: str | None = None
    summary: str | None = None
    document: dict[str, Any] | None = None
    documents: list[dict[str, Any]] | None = None
    error_code: str | None = None
    message: str | None = None


class WorkflowMergeResultsResponse(BaseModel):
    items: list[WorkflowMergeResultItem]


class LlmTestResult(BaseModel):
    text: str | None = None
    error: WorkflowStatusMessage | None = None


class LlmTestRequest(BaseModel):
    system_path: str
    user_path: str
    assistant_path: str = ""
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None


class MarkdownPreviewResponse(BaseModel):
    id: str
    markdown_file: str
    content: str


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

    system_prompt: str = ""
    assistant_prompt: str = ""
    temperature: float = Field(0.7, ge=0.0, le=2.0)


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

    system_prompt: str = ""
    assistant_prompt: str = ""
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class MdMrgSummarySettings(BaseModel):
    """md_mrg merge summary prompt configuration."""

    system_prompt: str = ""
    assistant_prompt: str = ""
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class MdMrgSettings(BaseModel):
    """Top-level md_mrg settings section."""

    model_config = ConfigDict(populate_by_name=True)

    score: MdMrgScoreSettings = Field(..., alias="merge_score")
    summary: MdMrgSummarySettings = Field(..., alias="merge_summary")


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
