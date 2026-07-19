export interface ModelEndpointSettings {
  endpoint: string
  model: string
  timeout_seconds: number
  max_retries: number
}

export interface MdGenSummarySettings {
  prompt_path: string
}

export interface MdGenImageSettings {
  max_longest_edge_px: number
  token_threshold: number
}

export interface MdGenSettings {
  summary: MdGenSummarySettings
  image: MdGenImageSettings
}

export interface MdMrgScoreSettings {
  prompt_path: string
}

export interface MdMrgSettings {
  score: MdMrgScoreSettings
}

export interface AppSettings {
  app_name: string
  version: string
  source_folder: string
  output_folder: string
  verbose: boolean
  overwrite: boolean
  ocr_model: ModelEndpointSettings
  language_model: ModelEndpointSettings
  md_gen: MdGenSettings
  md_mrg: MdMrgSettings
}

export interface ValidationError {
  loc: (string | number)[]
  msg: string
  type: string
}

export type WorkflowStageKey = 'start' | 'ocr' | 'merge' | 'rename'
export type WorkflowStageState =
  | 'unavailable'
  | 'enabled'
  | 'running'
  | 'complete'
  | 'failed'
  | 'selected'
export type WorkflowStatusSeverity = 'info' | 'success' | 'warning' | 'error'
export type WorkflowStageStatus = 'idle' | 'enabled' | 'running' | 'complete' | 'failed'
export type SourceFileType = 'pdf' | 'image'
export type FolderStatusKind =
  | 'not_configured'
  | 'missing'
  | 'not_directory'
  | 'inaccessible'
  | 'empty'
  | 'ready'

export interface WorkflowStatusMessage {
  severity: WorkflowStatusSeverity
  code: string
  message: string
}

export interface FolderStatus {
  path: string
  status: FolderStatusKind
  message: string
  item_count: number | null
}

export interface WorkflowSourceFile {
  id: string
  display_name: string
  absolute_path: string
  extension: string
  size_bytes: number
  source_type: SourceFileType
  order_index: number
  preview_url: string | null
}

export interface WorkflowMetrics {
  pdf_count: number
  image_count: number
  total_count: number
}

export interface WorkflowDiscoveryResponse {
  ok: boolean
  source_status: FolderStatus
  output_status: FolderStatus
  metrics: WorkflowMetrics
  items: WorkflowSourceFile[]
  messages: WorkflowStatusMessage[]
}

export interface WorkflowActiveItem {
  source_id: string | null
  display_name: string | null
  source_type: SourceFileType | null
  page_number: number | null
  markdown_file: string | null
}

export interface WorkflowActiveComparison {
  left_source_id: string | null
  right_source_id: string | null
  left_display_name: string | null
  right_display_name: string | null
}

export interface WorkflowCounts {
  markdown_count: number
  pdf_document_count: number
  image_group_count: number
}

export interface WorkflowProgress {
  stage: 'idle' | 'ocr' | 'planning' | 'merge'
  total_jobs: number
  completed_jobs: number
  percent: number
}

export type MergeItemStatus = 'pending' | 'running' | 'done' | 'failed'

export interface WorkflowMergeItem {
  id: string
  label: string
  item_type: 'pdf' | 'group'
  item_index: number
  status: MergeItemStatus
  output_pdf: string | null
  output_markdown: string | null
  error_code: string | null
  message: string | null
}

export interface WorkflowState {
  discovery: WorkflowDiscoveryResponse | null
  ocr_status: WorkflowStageStatus
  merge_status: WorkflowStageStatus
  progress: WorkflowProgress
  counts: WorkflowCounts
  current_item: WorkflowActiveItem | null
  active_comparison: WorkflowActiveComparison | null
  completed_item_ids: string[]
  active_merge_item_id: string | null
  merge_items: WorkflowMergeItem[]
  merge_results_available: boolean
  merge_result_error: WorkflowStatusMessage | null
  messages: WorkflowStatusMessage[]
  error: WorkflowStatusMessage | null
}

export interface EditablePlanDocumentBase {
  [key: string]: unknown
  id: string
  source_file_name: string
  file_type: SourceFileType
  markdown_file: string
  page_count?: number | null
  date_of_process?: string | null
  summary?: string | null
  status?: string | null
}

export interface EditableImagePage extends EditablePlanDocumentBase {
  kind: 'image_page'
  file_type: 'image'
}

export interface EditablePdfDocument extends EditablePlanDocumentBase {
  kind: 'pdf'
  file_type: 'pdf'
}

export interface EditableImageGroup {
  id: string
  kind: 'image_group'
  display_name: string
  documents: EditableImagePage[]
}

export type EditablePlanDocument = EditableImagePage | EditablePdfDocument
export type EditablePlanItem = EditableImageGroup | EditablePdfDocument

export interface EditableMergePlan {
  [key: string]: unknown
  items: EditablePlanItem[]
}

export interface MarkdownPreviewResponse {
  id: string
  markdown_file: string
  content: string
}

export interface DragPageState {
  pageId: string
  sourceGroupId: string
}

export type DropTarget =
  | { kind: 'inside-group'; groupId: string; index: number }
  | { kind: 'between-groups'; index: number }

export interface OcrTreeRow {
  id: string
  label: string
  status: 'pending' | 'running' | 'complete' | 'failed'
  source_id: string
}

export interface WorkflowMergeResultItem {
  id: string
  item_index: number
  item_type: 'pdf' | 'group'
  status: 'ok' | 'failed'
  label: string
  output_pdf: string | null
  output_markdown: string | null
  summary: string | null
  document: Record<string, unknown> | null
  documents: Record<string, unknown>[] | null
  error_code: string | null
  message: string | null
}

export interface WorkflowMergeResultsResponse {
  items: WorkflowMergeResultItem[]
}

export interface RenameRow {
  id: string
  current_name: string
  proposed_name: string
  status: 'unavailable' | 'simulated'
}
