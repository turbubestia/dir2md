"""Pydantic schemas for the webapp settings API.

These models describe the persisted JSON contract in ``data/config/settings.json``
as seen by the webapp. They intentionally mirror the on-disk shape so the
browser UI can load and save the shared configuration file without reshaping it.
"""

from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, Field, NonNegativeInt, PositiveFloat


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
