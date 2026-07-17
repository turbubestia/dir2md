# md_mrg Developer Guide

This document defines the current md_mrg planner/apply workflow and on-disk contracts.

## 1. Overview

md_mrg is the post-OCR consolidation stage. It runs in two explicit phases:

1. Plan phase: read `batch.json`, score adjacent image pages, and write `batch_mrg.json`.
2. Apply phase: read reviewed `batch_mrg.json`, produce merged artifacts, and write `batch_mrg_result.json`.

The module is local-first and uses `common.gateway.LlamaLanguageGateway` for pair scoring.

## 2. Planner Flow

Input: `source/batch.json`

- Load `documents` array from `batch.json`.
- Partition into image records (`file_type == "image"`) and non-image records (typically pdf).
- Score only adjacent image pairs.
- Group continuation rule:
  - continue group when `abs(score) >= 5`
  - split group when `abs(score) < 5`
  - split group when scoring fails (gateway error, markdown read error, parse error)
- Negative score handling:
  - if score is negative and threshold is met, Page B is inserted before Page A in the current group
  - next comparison remains anchored on Page A as requested by the project rule
- Emit every image group as an object with `documents` list, including singleton groups.
- Append original pdf records after all image groups.

Output: `source/batch_mrg.json`

## 3. Apply Flow

Input: `source/batch_mrg.json`

- Iterate `documents` in listed order.
- Group items (`{"documents": [...]}`):
  - merge markdown in listed order into `merger-NNN.md`
  - merge images in listed order into `merged-NNN.pdf`
  - delete only loose markdown files from this group after both merged files succeed
- Standalone pdf records are treated as passthrough status items.
- Continue processing later items if one group fails.
- Never delete original image files.

Output: `source/batch_mrg_result.json`

## 4. batch_mrg.json Schema

Top-level shape:

```json
{
  "documents": [
    {
      "documents": [
        {
          "source_file_name": "IMAG0003_scanned.jpg",
          "file_type": "image",
          "page_count": 1,
          "date_of_process": "2026-07-14T08:21:54.244888+00:00",
          "summary": "...",
          "markdown_file": "IMAG0003_scanned.md",
          "status": "ok"
        }
      ]
    },
    {
      "source_file_name": "contract.pdf",
      "file_type": "pdf",
      "page_count": 4,
      "date_of_process": "2026-07-14T08:21:54.244888+00:00",
      "summary": "...",
      "markdown_file": "contract.md",
      "status": "ok"
    }
  ]
}
```

Rules:

- Image groups always come first.
- Pdf records come after all image groups.
- Singleton image pages are encoded as group objects with one document.

## 5. batch_mrg_result.json Schema

Top-level shape:

```json
{
  "items": [
    {
      "item_index": 1,
      "item_type": "group",
      "status": "ok",
      "output_pdf": "merged-001.pdf",
      "output_markdown": "merger-001.md",
      "documents": []
    },
    {
      "item_index": 2,
      "item_type": "group",
      "status": "failed",
      "error_code": "group_markdown_read_failed",
      "message": "...",
      "documents": []
    },
    {
      "item_index": 3,
      "item_type": "pdf",
      "status": "ok",
      "document": {}
    }
  ]
}
```

Status semantics:

- `ok`: work item completed successfully.
- `failed`: work item failed but apply continued for later items.

## 6. Prompt Envelope Contract

Planner user prompt for each pair must use this exact marker structure:

```text
# Page A content
--- start of Page A content ---
{page_a_markdown}
--- end of Page A content ---

---

# Page B content
--- start of Page B content ---
{page_b_markdown}
--- end of Page B content ---
```
