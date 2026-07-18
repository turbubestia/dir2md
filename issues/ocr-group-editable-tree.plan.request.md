# OCR Group Editable Tree

WHen the OCR stage completes we end up with a `batch_mrg.json` with the document groups. PDF item will remain a single document item, while images becomes an array of document inside a document tag. The group list in the workflow must show each document group with a tree of each included single page images. This pages can still be selected and preview in the image preview and the markdown text loaded in the markdown text preview. Also the user will be able to move the pages in a group to manually sorte them if needed, but will will be able to move one page from one group to another (if a page was incorrectly place in a group). If a page is place in-between group the the page creates a new group.

## Goals

- Update the document group list to tree-like per document group
- Allow moving the pages inside and between groups (only for images)
- PDF does not participates in the move operations, PDF are a single document already.
- Before clicking the merge button, the new batch structure must be writen to `batch_mrg.json` so the `md_mrg.cli --apply` can work on the user decision.

## No Goals

- wire the merge stage that uses `md_mrg.cli --apply` is not part of this task but we do need to update the `batch_mrg.json` when the Merge button is click to make sure this updates works properly.

---
# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
The workflow UI must present OCR output document groups as an editable tree, where image-based documents expose their individual page images as movable child items while PDF-based documents remain single, non-movable document entries. Before the user starts the merge action, the application must persist the user's edited grouping and ordering decisions back to `batch_mrg.json` so the existing merge apply command can consume the updated batch structure.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement OCR-TREE-001:** Display Document Groups as an Editable Tree
	- **Description:** The workflow document group list must render each document group as a parent row with child rows for included single-page images. PDF documents must render as single document rows without child page movement controls.
	- **Acceptance Criteria:**
		- [ ] Given OCR has completed and `batch_mrg.json` contains image document groups, When the workflow group list is displayed, Then each image group appears as a tree parent with each included page image shown as a child item in its current order.
		- [ ] Given OCR has completed and `batch_mrg.json` contains a PDF document entry, When the workflow group list is displayed, Then the PDF appears as a single document item and does not expose page-level children for editing.
		- [ ] Given the user selects a page child item, When the selection changes, Then the image preview loads the selected page image and the markdown text preview loads that page's markdown content.

- **Requirement OCR-TREE-002:** Reorder Image Pages Within a Group
	- **Description:** Users must be able to change the order of image pages within the same document group before merging.
	- **Acceptance Criteria:**
		- [ ] Given an image group contains multiple page items, When the user moves one page above or below another page in the same group, Then the UI reflects the new order immediately.
		- [ ] Given a page has been reordered within its group, When the user clicks Merge, Then `batch_mrg.json` is updated with the reordered page sequence before merge execution begins.
		- [ ] Given a PDF document item is displayed, When the user attempts page reorder actions, Then no PDF page move operation is available or performed.

- **Requirement OCR-TREE-003:** Move Image Pages Between Groups
	- **Description:** Users must be able to move single-page image entries from one image document group to another image document group when OCR grouping placed a page incorrectly.
	- **Acceptance Criteria:**
		- [ ] Given at least two image groups exist, When the user moves a page from one group into another group, Then the source group removes the page and the target group includes it at the chosen position.
		- [ ] Given a moved page is selected after the move, When the preview panes refresh, Then the image preview and markdown text preview still point to the moved page's original source artifacts.
		- [ ] Given a PDF document item exists, When the user moves image pages, Then the PDF item cannot receive child image pages and cannot be moved into an image group as a page.

- **Requirement OCR-TREE-004:** Create a New Group by Placing a Page Between Groups
	- **Description:** If the user places a single image page between two document groups instead of inside an existing group, the application must create a new document group containing that page.
	- **Acceptance Criteria:**
		- [ ] Given image groups are displayed in the workflow list, When the user moves a page to a position between two groups, Then a new document group is created at that position containing only that page.
		- [ ] Given a new group is created from a moved page, When the user clicks Merge, Then `batch_mrg.json` includes the new group at the selected group position.
		- [ ] Given a source group loses its final page due to a move, When the move is completed, Then the application handles the empty source group according to the confirmed business rule.

- **Requirement OCR-TREE-005:** Persist Edited Batch Structure Before Merge
	- **Description:** The workflow must write the latest edited group structure to `batch_mrg.json` immediately before the Merge button's merge behavior proceeds, while keeping the actual `md_mrg.cli --apply` merge-stage wiring outside this task.
	- **Acceptance Criteria:**
		- [ ] Given the user has reordered pages, moved pages between groups, or created new groups, When the user clicks Merge, Then the updated group structure is written to `batch_mrg.json` before any merge-stage command would consume it.
		- [ ] Given the write to `batch_mrg.json` fails, When the user clicks Merge, Then the workflow surfaces an error and does not proceed as though the edited batch was saved.
		- [ ] Given no edits were made to the groups, When the user clicks Merge, Then the existing `batch_mrg.json` remains semantically equivalent and merge can proceed without unnecessary structure changes.

## 3. Scope & Constraints
- **In-Scope:**
	- Rendering OCR result groups in the workflow as a tree-like list.
	- Selecting image page children and loading the corresponding image and markdown previews.
	- Reordering image pages within a group.
	- Moving image pages between image groups.
	- Creating a new image group when a page is placed between groups.
	- Saving the edited batch group structure to `batch_mrg.json` when Merge is clicked.
	- Preventing PDFs from participating in page-level move operations.
	- **Out-of-Scope:**
	- Wiring or implementing the merge stage that runs `md_mrg.cli --apply`.
	- Editing OCR output content or markdown text content.
	- Splitting PDFs into editable page-level children.
	- Re-running OCR or regrouping automatically after manual edits.
	- **Technical Constraints / Edge Cases:**
	- The saved `batch_mrg.json` must remain compatible with the existing `md_mrg.cli --apply` input contract.
	- Page moves must preserve links to existing image and markdown artifacts.
	- PDF entries must be protected from drag/drop or movement operations that would alter them as page collections.
	- The behavior for image groups that become empty after moving their final page must be explicitly defined.
	- The UI must distinguish dropping a page inside a group from dropping it between groups clearly enough to avoid accidental group creation.

## 4. Open Design Choices (Questions for User)
- **[UX/UI]:** Should page movement be implemented with drag-and-drop, explicit up/down and move-to-group controls, or both?
**User: Only with drag-n-drop with a clear indication where it will be place, either with a single line highlighting the place or dinamically showing the item in the place, what ever is easier. The `Esc` key should cancel the move operation.**

- **[UX/UI]:** Should document groups be expandable/collapsible, and if so should groups default to expanded after OCR completes?
**User: it would be nice to have them expandable/collapsible and default to expanded after OCR completes.**

- **[Business Logic]:** When a page is moved out of a group and the source group becomes empty, should the empty group be deleted automatically or kept as an empty placeholder?
**User: should be deleted.**

- **[Business Logic]:** When a new group is created from a page placed between groups, how should the proposed output filename/group name be generated?
**User: At this point the `batch_mrg.json` doesn't define a merge document filename, so we can assign as sequential name like `DocumentGroup_N`.**

- **[Technical]:** Should the updated `batch_mrg.json` be saved only when Merge is clicked, or should every edit also be autosaved immediately for crash recovery?
**User: for now only when Merge is clicked.**

---
# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
The workflow UI must show OCR document groups as an editable, expandable tree where image groups expose movable page children and PDF documents remain single, non-editable entries. Users will adjust image page order and grouping with drag-and-drop only, and the application will persist the edited grouping to `batch_mrg.json` only when Merge is clicked.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement OCR-TREE-001:** Display OCR Groups as an Expanded Tree
	- **Description:** After OCR completes, the workflow document group list must render image-based document groups as expandable tree parents with page-level child rows, defaulting all groups to expanded. PDF-based entries must render as single document rows without page-level children or page movement affordances.
	- **Acceptance Criteria:**
		- [ ] Given OCR has completed and `batch_mrg.json` contains image document groups, When the workflow group list is displayed, Then each image group appears as an expanded tree parent with its page images shown as ordered child rows.
		- [ ] Given the user collapses or expands an image group, When the control is activated, Then the group hides or shows its page child rows without changing the saved group structure.
		- [ ] Given OCR has completed and `batch_mrg.json` contains a PDF document entry, When the workflow group list is displayed, Then the PDF appears as one document item and does not expose page-level children, drag handles, or drop targets.

- **Requirement OCR-TREE-002:** Select Page Children for Preview
	- **Description:** Page child rows in image groups must remain selectable so the existing image preview and markdown preview panes load the selected page's original artifacts.
	- **Acceptance Criteria:**
		- [ ] Given an image group page child is visible, When the user selects that page, Then the image preview loads the corresponding source page image.
		- [ ] Given an image group page child is selected, When the markdown preview is refreshed, Then it loads the markdown text associated with that page's original OCR output.
		- [ ] Given a page has been moved to another group or reordered, When the user selects it, Then both preview panes still resolve the page's original source image and markdown artifacts.

- **Requirement OCR-TREE-003:** Drag and Drop Image Pages Within Groups
	- **Description:** Users must reorder image page children within the same image group using drag-and-drop, with a clear visual insertion indicator during the operation and `Esc` cancel support.
	- **Acceptance Criteria:**
		- [ ] Given an image group contains multiple pages, When the user drags a page above or below another page in the same group and drops it, Then the UI immediately reflects the new page order.
		- [ ] Given a page drag operation is active, When the user hovers over a valid page insertion position, Then the UI shows a clear placement indicator such as an insertion line or live placeholder.
		- [ ] Given a page drag operation is active, When the user presses `Esc`, Then the drag operation is canceled and the page remains in its original group and position.
		- [ ] Given a PDF document item is displayed, When the user interacts with it, Then no page-level reorder operation is available or performed.

- **Requirement OCR-TREE-004:** Drag and Drop Image Pages Between Groups
	- **Description:** Users must move image page children from one image group into another image group using drag-and-drop while preserving page artifact references and preventing PDFs from participating in page movement.
	- **Acceptance Criteria:**
		- [ ] Given at least two image groups exist, When the user drags a page from one group into a valid position in another image group, Then the source group removes the page and the target group includes it at the dropped position.
		- [ ] Given a page is dragged over an image group, When the hover position is valid, Then the UI shows the exact insertion position before drop.
		- [ ] Given a page is moved between groups, When the move completes, Then the page retains its original image path, markdown path, and any existing metadata required by `md_mrg.cli --apply`.
		- [ ] Given a PDF document item exists, When the user drags an image page, Then the PDF item cannot receive the page and cannot itself be dragged as a page.

- **Requirement OCR-TREE-005:** Create New Image Groups from Between-Group Drops
	- **Description:** When a user drops an image page between two document groups instead of inside a group, the workflow must create a new image document group at that position containing only the dropped page.
	- **Acceptance Criteria:**
		- [ ] Given image groups are displayed, When the user drags a page to a valid between-group drop position and drops it, Then a new image group is created at that group position containing only that page.
		- [ ] Given a new group is created from a moved page, When the UI displays the group list, Then the new group uses the next sequential generated name in the format `DocumentGroup_N`.
		- [ ] Given the source group loses its final page due to a move, When the move completes, Then the empty source group is deleted automatically.
		- [ ] Given the user cancels a between-group drag with `Esc`, When the operation ends, Then no new group is created and the original grouping remains unchanged.

- **Requirement OCR-TREE-006:** Persist Edited Groups on Merge Click
	- **Description:** The workflow must write the latest edited group order and page membership to `batch_mrg.json` only when the user clicks Merge, before any merge-stage behavior would consume the batch file. This task does not wire or implement the actual `md_mrg.cli --apply` merge execution.
	- **Acceptance Criteria:**
		- [ ] Given the user has reordered pages, moved pages between groups, or created new groups, When the user clicks Merge, Then the updated group structure is written to `batch_mrg.json` before merge processing can proceed.
		- [ ] Given the user has made no group edits, When the user clicks Merge, Then the saved `batch_mrg.json` remains semantically equivalent to the existing batch structure.
		- [ ] Given writing `batch_mrg.json` fails, When the user clicks Merge, Then the workflow surfaces an error and does not continue as though the edited batch was saved.
		- [ ] Given a saved edited batch contains PDFs and image groups, When `md_mrg.cli --apply` reads it later, Then the file remains compatible with the existing merge apply input contract.

## 3. Scope & Constraints
- **In-Scope:**
	- Rendering OCR result groups in the workflow as expandable/collapsible tree rows defaulting to expanded after OCR completes.
	- Selecting image page child rows and loading the corresponding image and markdown previews.
	- Drag-and-drop reordering of image pages within the same image group.
	- Drag-and-drop movement of image pages between image groups.
	- Drag-and-drop creation of a new image group when a page is dropped between document groups.
	- Visual placement indication during drag-and-drop, using either an insertion line or live placeholder.
	- Canceling active drag operations with the `Esc` key.
	- Automatically deleting an image group that becomes empty after its final page is moved out.
	- Generating new group display names as sequential `DocumentGroup_N` values.
	- Saving the edited batch structure to `batch_mrg.json` only when Merge is clicked.
	- Preventing PDF entries from exposing page movement controls, receiving image pages, or being moved as page children.
	- **Out-of-Scope:**
	- Wiring or implementing the merge stage that runs `md_mrg.cli --apply`.
	- Autosaving group edits before Merge is clicked.
	- Editing OCR output content or markdown text content.
	- Splitting PDFs into editable page-level children.
	- Re-running OCR or automatically regrouping after manual edits.
	- Non-drag-and-drop movement controls such as up/down buttons or move-to-group menus.
	- **Technical Constraints / Edge Cases:**
	- The saved `batch_mrg.json` must remain compatible with the existing `md_mrg.cli --apply` input contract.
	- Page moves must preserve links to existing image, markdown, and metadata artifacts.
	- PDF entries must be protected from drag/drop operations that would alter them as page collections.
	- Between-group drop targets must be visually distinct from inside-group drop targets to avoid accidental group creation.
	- Empty image groups caused by moving the final page must be removed immediately from the in-memory UI state and from the batch structure saved on Merge.

**LOCKED**