import type {
  AppSettings,
  EditableImagePage,
  EditableMergePlan,
  EditablePdfDocument,
  MarkdownPreviewResponse,
  ValidationError,
  WorkflowDiscoveryResponse,
  WorkflowMergeResultItem,
  WorkflowMergeResultsResponse,
  WorkflowState,
  WorkflowSourceFile,
} from './types'

const API_BASE = ''
export const WORKFLOW_EVENTS_URL = `${API_BASE}/api/workflow/events`

export async function fetchSettings(): Promise<AppSettings> {
  const response = await fetch(`${API_BASE}/api/settings`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Failed to load settings (${response.status})`)
  }
  return response.json()
}

export interface SaveSettingsResult {
  ok: boolean
  settings?: AppSettings
  validationErrors?: ValidationError[]
  error?: string
}

export async function saveSettings(
  settings: AppSettings,
): Promise<SaveSettingsResult> {
  const response = await fetch(`${API_BASE}/api/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })

  if (response.status === 422) {
    const body = await response.json().catch(() => ({ detail: [] }))
    return {
      ok: false,
      validationErrors: Array.isArray(body.detail) ? body.detail : [],
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    return {
      ok: false,
      error: body.detail || `Save failed (${response.status})`,
    }
  }

  return { ok: true, settings: await response.json() }
}

export async function startWorkflowDiscovery(): Promise<WorkflowDiscoveryResponse> {
  const response = await fetch(`${API_BASE}/api/workflow/start`, {
    method: 'POST',
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Workflow start failed (${response.status})`)
  }

  return response.json()
}

export async function startWorkflowOcr(): Promise<WorkflowState> {
  const response = await fetch(`${API_BASE}/api/workflow/ocr`, {
    method: 'POST',
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Workflow OCR failed (${response.status})`)
  }

  return response.json()
}

export async function fetchWorkflowState(): Promise<WorkflowState> {
  const response = await fetch(`${API_BASE}/api/workflow/state`)

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Workflow state failed (${response.status})`)
  }

  return response.json()
}

export async function fetchEditableMergePlan(): Promise<EditableMergePlan> {
  const response = await fetch(`${API_BASE}/api/workflow/merge-plan`)

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Merge plan load failed (${response.status})`)
  }

  return response.json()
}

export async function saveEditableMergePlan(
  plan: EditableMergePlan,
): Promise<EditableMergePlan> {
  const response = await fetch(`${API_BASE}/api/workflow/merge-plan`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(plan),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Merge plan save failed (${response.status})`)
  }

  return response.json()
}

export async function startWorkflowMerge(plan: EditableMergePlan): Promise<WorkflowState> {
  const response = await fetch(`${API_BASE}/api/workflow/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Workflow merge failed (${response.status})`)
  }

  return response.json()
}

export async function fetchMergeResults(): Promise<WorkflowMergeResultsResponse> {
  const response = await fetch(`${API_BASE}/api/workflow/merge-results`)

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Merge results load failed (${response.status})`)
  }

  return response.json()
}

export function buildSourcePreviewUrl(
  item: WorkflowSourceFile,
): string | undefined {
  return item.preview_url ?? undefined
}

export function buildOcrArtifactPreviewUrl(
  item: EditableImagePage | EditablePdfDocument,
): string {
  return `${API_BASE}/api/workflow/ocr-preview/${encodeURIComponent(item.id)}`
}

export function buildMergeResultPdfPreviewUrl(item: WorkflowMergeResultItem): string {
  return `${API_BASE}/api/workflow/merge-result-preview/${encodeURIComponent(item.id)}`
}

export async function fetchMarkdownPreview(
  item: EditableImagePage | EditablePdfDocument,
): Promise<MarkdownPreviewResponse> {
  const response = await fetch(`${API_BASE}/api/workflow/markdown-preview/${encodeURIComponent(item.id)}`)

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Markdown preview failed (${response.status})`)
  }

  return response.json()
}

export async function fetchMergeResultMarkdown(item: WorkflowMergeResultItem): Promise<MarkdownPreviewResponse> {
  const response = await fetch(`${API_BASE}/api/workflow/merge-result-markdown/${encodeURIComponent(item.id)}`)

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Merge Markdown preview failed (${response.status})`)
  }

  return response.json()
}
