# Issue 1 - Save JSON metadata along with MD files

Current implementation has two path depending on the input
    - PDF: export individual pages as image compatible with the OCR model
    - Images: rescale to size compatible with OCR model
The it runs the OCR and writes as front matter some metadata to know at lease the source file of the text.

The we will use another language model to find the relation between the text documents to assemble multi-page scans.

However, for multi-page PDF we already know the page sequence and we must avoid this rediscovery.

## Goals

- Change the schema, instead save a JSON file with the page metadata instead of writing this as front matter (which also would make it more difficult to merge the multi-page markdown files into a single one).
- For multipage PDF save only one JSON file with the metadata and all the image/md files belonging to this document.
- Determine a JSON schema to allow identify whole documents (from multi-page PDF for example) from fragments.
- The JSON file will have the same prefix as the markdown
    - For single or multi page PDF it would looks like this
        - **source**: invoide_meal.pdf
        - **pages**: 3
        - **images**: `invoide_meal.page1.pdf`, `invoide_meal.page2.pdf`, `invoide_meal.page3.pdf`
        - **markdown**: `invoide_meal.page1.md`, `invoide_meal.page2.md`, `invoide_meal.page3.md`
        - **JSON**: `invoide_meal.json`
    - For individual images:
        - **source**: scan001.pdf
        - **pages**: 1
        - **images**: `scan001.pdf`
        - **markdown**: `scan001.md`
        - **JSON**: `scan001.json`
- For this the text from the extraction must be sent immediately to the language Qwen3-1.7B model which is server at http://localhost:8081. To the LLM we only need to ask for a short summary no longer than 3 lines.

```
System: You are an automated data-extraction parser. You process OCR text and output a consise summary no longer than three lines.

CRITICAL INSTRUCTIONS:
- DO NOT use thinking tags (<think>...</think>).
- DO NOT output any chain-of-thought reasoning, explanations, or introductory text.
- Failing to follow these rules will break the downstream parser system.

User: [Insert LightOnOCR Markdown Output]
```

   note we only need from the LLM the summary, the python code will produce the JSON file and metadata. The first and last line can be taken dirctly from the OCR text (limit to first line or first n words for example).

- The LightOnOCR-2 model is server at http://localhost:8080
- Save as default this endpoint so I don't have to pass them as options all the time.


## JSON Schema

Here is a designed JSON schema tailored to this workflow.

To bridge the gap between structured, multi-page documents (like PDFs) and fragmented assets (like individual scans that need relationship discovery), the schema uses a two-tier hierarchy: a top-level document structure and a detailed fragments array.

For multi-page PDFs, you write this once per document. For single scans, you write one per scan (which your downstream model can later analyze and merge by combining their fragments arrays into a new document JSON).

Se the file `src/md_gen/metadata-schema.json`

By extracting first_line and last_line directly into the JSON during the OCR pass, your downstream assembly script can check if a sentence splits across pages without opening and parsing large markdown strings. Once the order is determined, you can clean up the files by simply reading the array order and concatenating the .md targets.

### Concrete Examples
#### 1. Multi-Page PDF (invoice_meal.json)

Because is_verified_sequence is true, your downstream pipeline knows it can safely merge these markdown files sequentially without using an LLM to guess the order.

```json
{
  "document_id": "d3b07384-d113-495d-a342-d12534571234",
  "source_name": "invoice_meal.pdf",
  "total_pages": 3,
  "is_verified_sequence": true,
  "fragments": [
    {
      "sequence_number": 1,
      "image_file": "invoice_meal.page1.pdf",
      "markdown_file": "invoice_meal.page1.md",
      "anchors": {
        "first_line": "ACME CATERING LTD.",
        "last_line": "Itemized Description:",
        "page_header": "INVOICE #INV-2026-889",
        "page_footer": "Continued on Page 2"
      },
      "content_fingerprint": {
        "snippet": "Invoice from ACME Catering for corporate lunch event on July 7, 2026.",
        "detected_entities": ["ACME Catering", "INV-2026-889", "2026-07-07"]
      }
    },
    {
      "sequence_number": 2,
      "image_file": "invoice_meal.page2.pdf",
      "markdown_file": "invoice_meal.page2.md",
      "anchors": {
        "first_line": "1x Organic Salad Bar Platter ... $250.00",
        "last_line": "Total Balance Due: $1,420.00",
        "page_header": "INVOICE #INV-2026-889",
        "page_footer": "Page 2 of 2"
      },
      "content_fingerprint": {
        "snippet": "Line items for catering including salad bar, main course, and beverages. Total balance $1,420.00.",
        "detected_entities": ["INV-2026-889", "$1,420.00"]
      }
    }
  ]
}
```

#### 2. Individual Loose Scan (scan001.json)

When processing loose files, is_verified_sequence is set to false. Your relationship-discovery LLM can easily scan multiple individual JSON files, match the detected_entities (like matching invoice numbers) or evaluate if last_line from one file naturally flows into the first_line of another.

```json
{
  "document_id": "a112c334-e445-4a6d-b778-c88990011223",
  "source_name": "scan001.jpg",
  "total_pages": 1,
  "is_verified_sequence": false,
  "fragments": [
    {
      "sequence_number": 1,
      "image_file": "scan001.jpg",
      "markdown_file": "scan001.md",
      "anchors": {
        "first_line": "proposals must be submitted no later than Friday",
        "last_line": "to the department chair for review before",
        "page_header": "SECTION II: REQUIREMENTS",
        "page_footer": ""
      },
      "content_fingerprint": {
        "snippet": "Paragraph discussing proposal submission deadlines and institutional review requirements.",
        "detected_entities": ["Friday", "department chair"]
      }
    }
  ]
}
````

## Notes

Write you implementation analysis to the file `design/issues/1-save-json-metadata.plan.analysis.md`.
Do not write code yet.
Interview me for any design choise or ambiguities.
