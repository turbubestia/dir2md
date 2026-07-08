# Issue 3 - Implementation Plan for Loose Multi-Page Markdown Merging

Goal 2 focus on processing the documents and produce the OCR transcript save to a markdown file along with a JSON structure with metdata of the files. This goal focus on parsing this JSON data to find which single page scans are part of a multi-page document.

JSON files produced from a PDF have the property `"is_verified_sequence": true`, which mean it is self-contained and we can immediately merge the associated md files from the fragment description array, so we skip the merging steps.

For loose pages from scanned images, we start comparing pair of pages in a rolling window scheme. Comparing the summary along with trying to match the continuation of last line of page A to the first line of page B. For this we will use the same LLM use for the summary but in thinking mode, something like this

```
System: You are an expert document reconstruction engineer. Review the end of Page A and the start of Page B along with their summaries. Rate how naturally, grammatically, or contextually Page B continues Page A on a scale from 0 to 10.

Scoring Rules:
10 = Perfect grammatical fit (e.g., Page A ends with "the model achieved a total" and Page B starts with "accuracy of 94%").
7 = Paragraph split or graphic/table reference insertion (e.g., Page A ends a complete sentence mentioning "as seen in Table 1" and Page B begins with "Table 1 outlines...").
5 = Minimum continuity, like page A describe a concert ticket and page B describe terms of conditions.
4 = Similar content but unrelated document, for example a medical bill of different subject, electrical bills of different dates, etc.
3 = Major topic pivot, completely different structural style, or disjointed vocabulary.
0 = Totally unrelated pages.

Output raw JSON matching this schema: {"reason": "string", "bridge_score": integer}

User:
Page A End: "[Insert Page A last_sentence here]"
Page A Summary: "[Insert Page A summary]"
Page B Start: "[Insert Page B start here]"
Page B Summary: "[Insert Page B summary]"
```

If the score is at least 5 we consider the pages to belong to the same document, and we move page B to Page A JSON structure as the next fragments (kind of assembling the fragment array), so now Page A document would have 2 pages and 2 fragments. This has to be continue until no more pages can be merge. Would this be similar to a sort algorithm? We can be coparing forever, so there must be some deterministic exit criteria or algorithm.

## Goal

- This merger cli module (created in `src/md_mrg`) produce in a `mg-temp` a single JSON with an array of document structures (for consistency, we should update the `src/md_gen/metadata-schema.json` to allow an array of document objects).
- Later, the UI will load this generated merging scheme to present this to the user. The user will be able to modify it and when accepted will generate a new one.
- The same md-mrg module can receive this single JSON (think of it as a batch file) and will start merging all fragments markdown, will also merge the source images into multipage PDF (this will require an image to PDF library) and save them (the markdown and PDF) to the output folder. The markdown will have a front matter with some metadata (like date of generation, source PDF file, topic, summary)
- For the merged markdown, we will use also the LLM to generate a summary combining the summary of each page.

## Task

Base on the description and goal perform an implementation analysis describing how to achieve the goals.

## Notes

Write the analysis to the file `design/issues/3-merge-muti-page-ocr.plan.analysis.md`.
Interview me for any design choice or ambiguity.
Dont write code yet.