import type {
  AppSettings,
  ValidationError,
  WorkflowDiscoveryResponse,
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

export function buildSourcePreviewUrl(
  item: WorkflowSourceFile,
): string | undefined {
  return item.preview_url ?? undefined
}
