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
  | 'selected'
export type WorkflowStatusSeverity = 'info' | 'success' | 'warning' | 'error'
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

export interface OcrTreeRow {
  id: string
  label: string
  status: 'pending' | 'simulated'
  source_id: string
}

export interface MergeRow {
  id: string
  title: string
  item_count: number
  status: 'pending' | 'simulated'
}

export interface RenameRow {
  id: string
  current_name: string
  proposed_name: string
  status: 'unavailable' | 'simulated'
}
