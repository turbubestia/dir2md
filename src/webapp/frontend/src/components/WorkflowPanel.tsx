import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { MathJax, MathJaxContext } from 'better-react-mathjax'
import { Document, Page, pdfjs } from 'react-pdf'
import ReactMarkdown from 'react-markdown'
import rehypeMathjax from 'rehype-mathjax/svg'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import {
  WORKFLOW_EVENTS_URL,
  buildMergeResultPdfPreviewUrl,
  buildOcrArtifactPreviewUrl,
  buildSourcePreviewUrl,
  fetchEditableMergePlan,
  fetchMergeResultMarkdown,
  fetchMergeResults,
  fetchMarkdownPreview,
  fetchWorkflowState,
  startWorkflowDiscovery,
  startWorkflowMerge,
  startWorkflowOcr,
} from '../api'
import type {
  DragPageState,
  DropTarget,
  EditableImageGroup,
  EditableImagePage,
  EditableMergePlan,
  EditablePlanDocument,
  EditablePlanItem,
  MarkdownPreviewResponse,
  RenameRow,
  WorkflowDiscoveryResponse,
  WorkflowMergeItem,
  WorkflowMergeResultItem,
  WorkflowState,
  WorkflowSourceFile,
  WorkflowStageKey,
  WorkflowStageState,
  WorkflowStatusMessage,
} from '../types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const STAGES: { key: WorkflowStageKey; label: string }[] = [
  { key: 'start', label: 'Start' },
  { key: 'ocr', label: 'OCR' },
  { key: 'merge', label: 'Merge' },
  { key: 'rename', label: 'Rename' },
]

type StageStatusLine = { label: string; value: string }
type SourceOcrStatus = 'pending' | 'running' | 'done' | 'failed'
type PdfZoomMode = 'fit-width' | 'fit-height' | 'actual-size' | 'custom'
type MarkdownPreviewStatus = 'idle' | 'loading' | 'ready' | 'error'
type MarkdownViewMode = 'code' | 'preview'
type PdfPanState = {
  pointerId: number
  startX: number
  startY: number
  scrollLeft: number
  scrollTop: number
}

const PDF_CSS_PIXELS_PER_POINT = 96 / 72

const INITIAL_STAGE_STATES: Record<WorkflowStageKey, WorkflowStageState> = {
  start: 'enabled',
  ocr: 'unavailable',
  merge: 'unavailable',
  rename: 'unavailable',
}

const EMPTY_METRICS = { pdf_count: 0, image_count: 0, total_count: 0 }
const EMPTY_ITEMS: WorkflowSourceFile[] = []
const MARKDOWN_SANITIZE_SCHEMA = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...(defaultSchema.attributes?.code ?? []),
      ['className', 'language-math', 'math-inline', 'math-display'],
    ],
  },
  tagNames: [...(defaultSchema.tagNames ?? []), 'mark'],
}

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function nextWarning(stage: string): WorkflowStatusMessage {
  return {
    severity: 'warning',
    code: 'stage_unavailable',
    message: `${stage} is not available until the previous stage is complete.`,
  }
}

function displayCount(hasValue: boolean, value: number): string {
  return hasValue ? String(value) : '-'
}

function stageStatusLines({
  stage,
  hasDiscovery,
  metrics,
  workflowState,
  mergeRows,
  renameRows,
}: {
  stage: WorkflowStageKey
  hasDiscovery: boolean
  metrics: typeof EMPTY_METRICS
  workflowState: WorkflowState | null
  mergeRows: WorkflowMergeResultItem[]
  renameRows: RenameRow[]
}): StageStatusLine[] {
  if (stage === 'start') {
    return [
      { label: 'PDF Files', value: displayCount(hasDiscovery, metrics.pdf_count) },
      { label: 'Image Files', value: displayCount(hasDiscovery, metrics.image_count) },
    ]
  }

  if (stage === 'ocr') {
    const counts = workflowState?.counts
    return [
      { label: 'Markdown Files', value: displayCount(hasDiscovery, counts?.markdown_count ?? 0) },
      { label: 'PDF Documents', value: displayCount(hasDiscovery, counts?.pdf_document_count ?? 0) },
      { label: 'Image Groups', value: displayCount(hasDiscovery, counts?.image_group_count ?? 0) },
    ]
  }

  if (stage === 'merge') {
    const itemCount = mergeRows.length || workflowState?.merge_items.length || 0
    return [{ label: 'Documents', value: itemCount > 0 ? String(itemCount) : '-' }]
  }

  return [{ label: 'Documents', value: renameRows.length > 0 ? String(renameRows.length) : '-' }]
}

function connectorState(
  stage: WorkflowStageKey,
  nextStage: WorkflowStageKey,
  stageStates: Record<WorkflowStageKey, WorkflowStageState>,
): 'complete' | 'running' | 'inactive' {
  if (stageStates[nextStage] === 'running' || stageStates[stage] === 'running') {
    return 'running'
  }
  if (stageStates[stage] === 'complete') {
    return 'complete'
  }
  return 'inactive'
}

function stageButtonFillClass(state: WorkflowStageState): string {
  if (state === 'failed') {
    return 'bg-red-950 border-red-500 text-red-100'
  }
  if (state === 'running' || state === 'complete' || state === 'selected') {
    return 'bg-accent-dim border-accent text-white'
  }
  return 'bg-sky-200 border-sky-200 text-slate-950'
}

function stageProgressPercent(stage: WorkflowStageKey): number {
  const stageIndex = STAGES.findIndex((candidate) => candidate.key === stage)
  if (stageIndex <= 0) {
    return 0
  }
  return (stageIndex / (STAGES.length - 1)) * 100
}

function sourceOcrStatus(item: WorkflowSourceFile, workflowState: WorkflowState | null): SourceOcrStatus | null {
  if (!workflowState || workflowState.ocr_status === 'idle' || workflowState.ocr_status === 'enabled') {
    return null
  }
  if (workflowState.ocr_status === 'complete' || workflowState.completed_item_ids.includes(item.id)) {
    return 'done'
  }
  if (workflowState.current_item?.source_id === item.id) {
    return 'running'
  }
  if (workflowState.ocr_status === 'failed') {
    return 'failed'
  }
  return 'pending'
}

function sourceOcrStatusColor(status: SourceOcrStatus): string {
  if (status === 'done') {
    return '#6ee7b7'
  }
  if (status === 'failed') {
    return '#fca5a5'
  }
  return '#94a3b8'
}

function ocrStageState(workflowState: WorkflowState | null, hasDiscovery: boolean): WorkflowStageState {
  if (!hasDiscovery) {
    return 'unavailable'
  }
  if (workflowState?.ocr_status === 'running') {
    return 'running'
  }
  if (workflowState?.ocr_status === 'complete') {
    return 'complete'
  }
  if (workflowState?.ocr_status === 'failed') {
    return 'failed'
  }
  return 'enabled'
}

function mergeStageState(workflowState: WorkflowState | null): WorkflowStageState {
  if (workflowState?.ocr_status !== 'complete') {
    return 'unavailable'
  }
  if (workflowState.merge_status === 'running') {
    return 'running'
  }
  if (workflowState.merge_status === 'complete') {
    return 'complete'
  }
  if (workflowState.merge_status === 'failed') {
    return 'failed'
  }
  return 'enabled'
}

function mergeStatusLabel(status: WorkflowMergeItem['status']): string {
  if (status === 'done') {
    return 'done'
  }
  return status
}

function mergeStatusColor(status: WorkflowMergeItem['status']): string {
  if (status === 'done') {
    return '#6ee7b7'
  }
  if (status === 'failed') {
    return '#fca5a5'
  }
  return '#94a3b8'
}

function isImageGroup(item: EditablePlanItem): item is EditableImageGroup {
  return item.kind === 'image_group'
}

function planDocuments(plan: EditableMergePlan | null): EditablePlanDocument[] {
  if (!plan) {
    return []
  }
  return plan.items.flatMap((item): EditablePlanDocument[] => (isImageGroup(item) ? item.documents : [item]))
}

function findPlanDocument(plan: EditableMergePlan | null, id: string | null): EditablePlanDocument | null {
  if (!id) {
    return null
  }
  return planDocuments(plan).find((document) => document.id === id) ?? null
}

function cloneEditablePlan(plan: EditableMergePlan): EditableMergePlan {
  return JSON.parse(JSON.stringify(plan)) as EditableMergePlan
}

function findPageLocation(plan: EditableMergePlan, pageId: string): { groupIndex: number; pageIndex: number } | null {
  for (let groupIndex = 0; groupIndex < plan.items.length; groupIndex += 1) {
    const item = plan.items[groupIndex]
    if (!isImageGroup(item)) {
      continue
    }
    const pageIndex = item.documents.findIndex((document) => document.id === pageId)
    if (pageIndex >= 0) {
      return { groupIndex, pageIndex }
    }
  }
  return null
}

function nextGroupLabel(plan: EditableMergePlan): string {
  const nextIndex = plan.items.filter(isImageGroup).length + 1
  return `DocumentGroup_${nextIndex}`
}

function movePage(plan: EditableMergePlan, pageId: string, target: DropTarget): EditableMergePlan {
  const nextPlan = cloneEditablePlan(plan)
  const location = findPageLocation(nextPlan, pageId)
  if (!location) {
    return plan
  }

  const sourceGroup = nextPlan.items[location.groupIndex]
  if (!isImageGroup(sourceGroup)) {
    return plan
  }

  if (target.kind === 'inside-group' && sourceGroup.id === target.groupId) {
    const [page] = sourceGroup.documents.splice(location.pageIndex, 1)
    const adjustedIndex = target.index > location.pageIndex ? target.index - 1 : target.index
    sourceGroup.documents.splice(Math.max(0, Math.min(adjustedIndex, sourceGroup.documents.length)), 0, page)
    return nextPlan
  }

  const [page] = sourceGroup.documents.splice(location.pageIndex, 1)
  let removedSourceBeforeTarget = false
  if (sourceGroup.documents.length === 0) {
    nextPlan.items.splice(location.groupIndex, 1)
    removedSourceBeforeTarget = true
  }

  if (target.kind === 'inside-group') {
    const targetGroup = nextPlan.items.find((item): item is EditableImageGroup => isImageGroup(item) && item.id === target.groupId)
    if (!targetGroup) {
      return plan
    }
    targetGroup.documents.splice(Math.max(0, Math.min(target.index, targetGroup.documents.length)), 0, page)
    return nextPlan
  }

  const targetIndex = removedSourceBeforeTarget && location.groupIndex < target.index ? target.index - 1 : target.index
  const displayName = nextGroupLabel(nextPlan)
  nextPlan.items.splice(Math.max(0, Math.min(targetIndex, nextPlan.items.length)), 0, {
    id: `group-${Date.now()}`,
    kind: 'image_group',
    display_name: displayName,
    documents: [page],
  })
  return nextPlan
}

export default function WorkflowPanel() {
  const [selectedStage, setSelectedStage] = useState<WorkflowStageKey>('start')
  const [progressStage, setProgressStage] = useState<WorkflowStageKey>('start')
  const [stageStates, setStageStates] =
    useState<Record<WorkflowStageKey, WorkflowStageState>>(INITIAL_STAGE_STATES)
  const [discovery, setDiscovery] = useState<WorkflowDiscoveryResponse | null>(null)
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [editablePlan, setEditablePlan] = useState<EditableMergePlan | null>(null)
  const [expandedGroupIds, setExpandedGroupIds] = useState<Set<string>>(new Set())
  const [selectedPlanItemId, setSelectedPlanItemId] = useState<string | null>(null)
  const [dragState, setDragState] = useState<DragPageState | null>(null)
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null)
  const [dragSnapshot, setDragSnapshot] = useState<EditableMergePlan | null>(null)
  const [markdownPreview, setMarkdownPreview] = useState<MarkdownPreviewResponse | null>(null)
  const [markdownPreviewStatus, setMarkdownPreviewStatus] = useState<MarkdownPreviewStatus>('idle')
  const [markdownViewMode, setMarkdownViewMode] = useState<MarkdownViewMode>('preview')
  const [messages, setMessages] = useState<WorkflowStatusMessage[]>([])
  const [mergeRows, setMergeRows] = useState<WorkflowMergeResultItem[]>([])
  const [selectedMergeResultId, setSelectedMergeResultId] = useState<string | null>(null)
  const [renameRows, setRenameRows] = useState<RenameRow[]>([])
  const [timerId, setTimerId] = useState<number | null>(null)
  const hasAutoSelectedOcrAfterComplete = useRef(false)
  const planLoadRequested = useRef(false)

  useEffect(() => {
    return () => {
      if (timerId !== null) {
        window.clearTimeout(timerId)
      }
    }
  }, [timerId])

  useEffect(() => {
    let cancelled = false
    let eventSource: EventSource | null = null

    async function loadPlanAfterComplete() {
      if (planLoadRequested.current) {
        return
      }
      planLoadRequested.current = true
      try {
        const plan = await fetchEditableMergePlan()
        if (cancelled) {
          return
        }
        setEditablePlan(plan)
        setExpandedGroupIds(new Set(plan.items.filter(isImageGroup).map((item) => item.id)))
        setSelectedPlanItemId((current) => current ?? planDocuments(plan)[0]?.id ?? null)
      } catch (error) {
        if (!cancelled) {
          setMessages([
            {
              severity: 'error',
              code: 'merge_plan_load_failed',
              message: error instanceof Error ? error.message : 'Editable merge plan could not be loaded.',
            },
          ])
        }
      }
    }

    async function loadMergeResults() {
      try {
        const results = await fetchMergeResults()
        if (cancelled) {
          return
        }
        setMergeRows(results.items)
        setSelectedMergeResultId((current) => current ?? results.items.find((item) => item.status === 'ok')?.id ?? results.items[0]?.id ?? null)
      } catch (error) {
        if (!cancelled) {
          setMessages([
            {
              severity: 'error',
              code: 'merge_results_load_failed',
              message: error instanceof Error ? error.message : 'Merge results could not be loaded.',
            },
          ])
        }
      }
    }

    function applyState(nextState: WorkflowState) {
      if (cancelled) {
        return
      }
      setWorkflowState(nextState)
      if (nextState.discovery) {
        setDiscovery(nextState.discovery)
        setSelectedSourceId((current) => current ?? nextState.discovery?.items[0]?.id ?? null)
      }
      setMessages(nextState.messages)
      if (nextState.ocr_status === 'complete') {
        void loadPlanAfterComplete()
      }
      if (nextState.merge_status === 'running') {
        setSelectedStage('merge')
        setProgressStage('merge')
      }
      if (nextState.merge_results_available) {
        void loadMergeResults()
      }
    }

    void fetchWorkflowState()
      .then(applyState)
      .catch((error) => {
        if (!cancelled) {
          setMessages([
            {
              severity: 'error',
              code: 'state_failed',
              message: error instanceof Error ? error.message : 'Workflow state failed.',
            },
          ])
        }
      })

    eventSource = new EventSource(WORKFLOW_EVENTS_URL)
    eventSource.addEventListener('workflow_state', (event) => {
      try {
        applyState(JSON.parse((event as MessageEvent).data) as WorkflowState)
      } catch {
        setMessages([{ severity: 'error', code: 'state_event_invalid', message: 'Workflow update could not be read.' }])
      }
    })
    eventSource.onerror = () => {
      void fetchWorkflowState().then(applyState).catch(() => undefined)
    }

    return () => {
      cancelled = true
      eventSource?.close()
    }
  }, [])

  const items = discovery?.items ?? EMPTY_ITEMS
  const selectedSource =
    items.find((item) => item.id === selectedSourceId) ?? items[0] ?? null
  const selectedPlanItem = findPlanDocument(editablePlan, selectedPlanItemId)
  const selectedMergeResult = mergeRows.find((item) => item.id === selectedMergeResultId) ?? null
  const metrics = discovery?.metrics ?? EMPTY_METRICS
  const hasDiscovery = discovery !== null
  const progressPercent = workflowState?.merge_status === 'running'
    ? stageProgressPercent('merge')
    : workflowState?.ocr_status === 'complete'
    ? 100
    : workflowState?.ocr_status === 'running'
      ? workflowState.progress.percent
      : stageProgressPercent(progressStage)
  const isStageRunning = workflowState?.ocr_status === 'running'
    || workflowState?.merge_status === 'running'
    || Object.values(stageStates).some((state) => state === 'running')

  useEffect(() => {
    setStageStates((current) => ({
      ...current,
      start: discovery?.ok ? 'complete' : 'enabled',
      ocr: ocrStageState(workflowState, hasDiscovery),
      merge: mergeStageState(workflowState),
      rename: workflowState?.merge_status === 'complete' && workflowState.merge_results_available
        ? current.rename === 'complete' ? 'complete' : 'enabled'
        : current.rename === 'complete' ? 'complete' : 'unavailable',
    }))
  }, [discovery, hasDiscovery, items, workflowState])

  useEffect(() => {
    if (selectedStage === 'merge') {
      if (!selectedMergeResult || selectedMergeResult.status !== 'ok') {
        setMarkdownPreview(null)
        setMarkdownPreviewStatus('idle')
        return
      }

      let cancelled = false
      setMarkdownPreview(null)
      setMarkdownPreviewStatus('loading')
      void fetchMergeResultMarkdown(selectedMergeResult)
        .then((preview) => {
          if (!cancelled) {
            setMarkdownPreview(preview)
            setMarkdownPreviewStatus('ready')
          }
        })
        .catch(() => {
          if (!cancelled) {
            setMarkdownPreviewStatus('error')
          }
        })

      return () => {
        cancelled = true
      }
    }

    if (selectedStage !== 'ocr' || !selectedPlanItem) {
      setMarkdownPreview(null)
      setMarkdownPreviewStatus('idle')
      return
    }

    let cancelled = false
    setMarkdownPreview(null)
    setMarkdownPreviewStatus('loading')
    void fetchMarkdownPreview(selectedPlanItem)
      .then((preview) => {
        if (!cancelled) {
          setMarkdownPreview(preview)
          setMarkdownPreviewStatus('ready')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMarkdownPreviewStatus('error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [selectedMergeResult, selectedPlanItem, selectedStage])

  useEffect(() => {
    if (!dragState) {
      return
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (dragSnapshot) {
          setEditablePlan(dragSnapshot)
        }
        setDragState(null)
        setDropTarget(null)
        setDragSnapshot(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [dragSnapshot, dragState])

  useEffect(() => {
    if (workflowState?.ocr_status === 'complete' && !hasAutoSelectedOcrAfterComplete.current) {
      hasAutoSelectedOcrAfterComplete.current = true
      setSelectedStage('ocr')
      setProgressStage('ocr')
    }
    if (workflowState?.ocr_status !== 'complete') {
      hasAutoSelectedOcrAfterComplete.current = false
    }
  }, [workflowState?.ocr_status])

  function clearPendingTimer() {
    if (timerId !== null) {
      window.clearTimeout(timerId)
      setTimerId(null)
    }
  }

  async function runStart() {
    clearPendingTimer()
    setSelectedStage('start')
    setProgressStage('start')
    setStageStates({ ...INITIAL_STAGE_STATES, start: 'running' })
    setEditablePlan(null)
    setExpandedGroupIds(new Set())
    setSelectedPlanItemId(null)
    setDragState(null)
    setDropTarget(null)
    setDragSnapshot(null)
    setMarkdownPreview(null)
    setMarkdownPreviewStatus('idle')
    setMergeRows([])
    setSelectedMergeResultId(null)
    setRenameRows([])
    setSelectedSourceId(null)
    hasAutoSelectedOcrAfterComplete.current = false
    planLoadRequested.current = false
    setMessages([{ severity: 'info', code: 'start_running', message: 'Reading configured source folder.' }])

    try {
      const response = await startWorkflowDiscovery()
      setDiscovery(response)
      setWorkflowState(null)
      setSelectedSourceId(response.items[0]?.id ?? null)
      setMessages(response.messages)
      setStageStates({
        start: response.ok ? 'complete' : 'enabled',
        ocr: response.ok && response.metrics.total_count > 0 ? 'enabled' : 'unavailable',
        merge: 'unavailable',
        rename: 'unavailable',
      })
    } catch (error) {
      setDiscovery(null)
      setStageStates(INITIAL_STAGE_STATES)
      setMessages([
        {
          severity: 'error',
          code: 'start_failed',
          message: error instanceof Error ? error.message : 'Workflow start failed.',
        },
      ])
    }
  }

  async function runBackendOcr() {
    if (stageStates.ocr === 'unavailable') {
      setMessages([nextWarning('OCR')])
      return
    }
    if (workflowState?.ocr_status === 'running') {
      return
    }

    clearPendingTimer()
    setProgressStage('ocr')
    setStageStates((current) => ({ ...current, ocr: 'running' }))
    setEditablePlan(null)
    setExpandedGroupIds(new Set())
    setSelectedPlanItemId(null)
    setMarkdownPreview(null)
    setMarkdownPreviewStatus('idle')
    setMergeRows([])
    setSelectedMergeResultId(null)
    planLoadRequested.current = false
    setMessages([{ severity: 'info', code: 'ocr_starting', message: 'Starting OCR.' }])

    try {
      const state = await startWorkflowOcr()
      setWorkflowState(state)
      setMessages(state.messages)
    } catch (error) {
      setStageStates((current) => ({ ...current, ocr: 'failed' }))
      setMessages([
        {
          severity: 'error',
          code: 'ocr_failed',
          message: error instanceof Error ? error.message : 'OCR failed to start.',
        },
      ])
    }
  }

  function runSimulatedStage(stage: Exclude<WorkflowStageKey, 'start' | 'ocr' | 'merge'>) {
    const label = STAGES.find((candidate) => candidate.key === stage)?.label ?? stage
    if (stageStates[stage] === 'unavailable') {
      setMessages([nextWarning(label)])
      return
    }
    if (stageStates[stage] === 'running') {
      return
    }

    clearPendingTimer()
    setSelectedStage(stage)
    setStageStates((current) => ({ ...current, [stage]: 'running' }))
    setMessages([{ severity: 'info', code: `${stage}_running`, message: `${label} simulation is running.` }])

    const nextTimerId = window.setTimeout(() => {
      if (stage === 'rename') {
        setRenameRows([
          {
            id: 'rename-preview',
            current_name: 'Simulated document group',
            proposed_name: 'Unavailable until merge implementation',
            status: 'unavailable',
          },
        ])
        setStageStates((current) => ({ ...current, rename: 'complete' }))
      }
      setMessages([{ severity: 'success', code: `${stage}_complete`, message: `${label} placeholder completed.` }])
      setTimerId(null)
    }, 650)

    setTimerId(nextTimerId)
  }

  async function runMergeStage() {
    if (stageStates.merge === 'unavailable') {
      setMessages([nextWarning('Merge')])
      return
    }
    if (stageStates.merge === 'running') {
      return
    }
    if (!editablePlan) {
      setMessages([{ severity: 'error', code: 'merge_plan_missing', message: 'Editable merge plan is not loaded.' }])
      setStageStates((current) => ({ ...current, merge: 'enabled' }))
      return
    }

    clearPendingTimer()
    setSelectedStage('merge')
    setProgressStage('merge')
    setStageStates((current) => ({ ...current, merge: 'running' }))
    setMergeRows([])
    setSelectedMergeResultId(null)
    setMarkdownPreview(null)
    setMarkdownPreviewStatus('idle')
    setMessages([{ severity: 'info', code: 'merge_starting', message: 'Starting merge.' }])

    try {
      const state = await startWorkflowMerge(editablePlan)
      setWorkflowState(state)
      setMessages(state.messages)
    } catch (error) {
      setStageStates((current) => ({ ...current, merge: 'enabled' }))
      setMessages([
        {
          severity: 'error',
          code: 'merge_failed',
          message: error instanceof Error ? error.message : 'Merge could not be started.',
        },
      ])
    }
  }

  function handleStageClick(stage: WorkflowStageKey) {
    if (isStageRunning) {
      return
    }
    setProgressStage(stage)
    if (stage === 'start') {
      void runStart()
      return
    }
    if (stage === 'ocr') {
      void runBackendOcr()
      return
    }
    if (stage === 'merge') {
      void runMergeStage()
      return
    }
    runSimulatedStage(stage)
  }

  return (
    <section className="workflow-root">
      <div className="workflow-toolbar">
        <div className="workflow-stage-rail" aria-label="Workflow stages">
          <div
            className="workflow-stage-progress"
            style={{ width: `${progressPercent}%` }}
            aria-hidden="true"
          />
          <div className="workflow-stage-grid">
            {STAGES.map((stage, index) => {
              const state = selectedStage === stage.key ? 'selected' : stageStates[stage.key]
              const isDisabled = isStageRunning || stageStates[stage.key] === 'unavailable'
              const nextStage = STAGES[index + 1]?.key
              const outgoingState = nextStage ? connectorState(stage.key, nextStage, stageStates) : 'none'
              const lines = stageStatusLines({
                stage: stage.key,
                hasDiscovery,
                metrics,
                workflowState,
                mergeRows,
                renameRows,
              })
              return (
                <div
                  key={stage.key}
                  className={`workflow-stage-block workflow-stage-block-${outgoingState}`}
                >
                  <button
                    type="button"
                    disabled={isDisabled}
                    onClick={() => handleStageClick(stage.key)}
                    className={`workflow-stage workflow-stage-${state} ${stageButtonFillClass(state)}`}
                    aria-pressed={selectedStage === stage.key}
                    aria-disabled={isDisabled}
                  >
                    <span>{stage.label}</span>
                  </button>
                  <div className="workflow-stage-status">
                    {lines.map((line) => (
                      <span key={line.label}>
                        <span>{line.label}</span>
                        <strong>{line.value}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="workflow-panels">
        <section className="workflow-panel workflow-list-panel">
          <PanelTitle stage={selectedStage} />
          <LeftPanel
            selectedStage={selectedStage}
            items={items}
            selectedSourceId={selectedSource?.id ?? null}
            editablePlan={editablePlan}
            expandedGroupIds={expandedGroupIds}
            selectedPlanItemId={selectedPlanItemId}
            dragState={dragState}
            dropTarget={dropTarget}
            mergeRows={mergeRows}
            selectedMergeResultId={selectedMergeResultId}
            renameRows={renameRows}
            onSelectSource={setSelectedSourceId}
            onSelectPlanItem={setSelectedPlanItemId}
            onSelectMergeResult={setSelectedMergeResultId}
            onToggleGroup={(groupId) => {
              setExpandedGroupIds((current) => {
                const next = new Set(current)
                if (next.has(groupId)) {
                  next.delete(groupId)
                } else {
                  next.add(groupId)
                }
                return next
              })
            }}
            onDragStart={(page, groupId) => {
              if (!editablePlan) {
                return
              }
              setDragState({ pageId: page.id, sourceGroupId: groupId })
              setDragSnapshot(cloneEditablePlan(editablePlan))
            }}
            onDropTargetChange={setDropTarget}
            onDropPage={(target) => {
              if (!editablePlan || !dragState) {
                return
              }
              const nextPlan = movePage(editablePlan, dragState.pageId, target)
              setEditablePlan(nextPlan)
              setExpandedGroupIds(new Set(nextPlan.items.filter(isImageGroup).map((item) => item.id)))
              setSelectedPlanItemId(dragState.pageId)
              setDragState(null)
              setDropTarget(null)
              setDragSnapshot(null)
            }}
            onDragEnd={() => {
              setDragState(null)
              setDropTarget(null)
              setDragSnapshot(null)
            }}
            workflowState={workflowState}
            isStageRunning={isStageRunning}
          />
        </section>
        <section className="workflow-panel workflow-preview-panel">
          <h3 className="workflow-panel-title">Document preview</h3>
          <MiddlePanel selectedStage={selectedStage} selectedSource={selectedSource} selectedPlanItem={selectedPlanItem} selectedMergeResult={selectedMergeResult} />
        </section>
        <section className="workflow-panel workflow-preview-panel">
          <div className="workflow-panel-heading">
            <h3 className="workflow-panel-title">Markdown</h3>
            <div className="workflow-markdown-toggle" role="group" aria-label="Markdown view mode">
              {(['code', 'preview'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={markdownViewMode === mode ? 'workflow-markdown-toggle-active' : ''}
                  aria-pressed={markdownViewMode === mode}
                  onClick={() => setMarkdownViewMode(mode)}
                >
                  {mode === 'code' ? 'Code' : 'Preview'}
                </button>
              ))}
            </div>
          </div>
          <RightPanel
            selectedStage={selectedStage}
            selectedSource={selectedSource}
            selectedPlanItem={selectedPlanItem}
            selectedMergeResult={selectedMergeResult}
            markdownPreview={markdownPreview}
            markdownPreviewStatus={markdownPreviewStatus}
            markdownViewMode={markdownViewMode}
          />
        </section>
      </div>

      <StatusArea messages={messages} discovery={discovery} />
    </section>
  )
}

function StatusArea({
  messages,
  discovery,
}: {
  messages: WorkflowStatusMessage[]
  discovery: WorkflowDiscoveryResponse | null
}) {
  const statusMessages = messages.length > 0 ? messages : [{ severity: 'info' as const, code: 'idle', message: 'Start discovery has not run.' }]
  return (
    <div className="workflow-status-area">
      {discovery ? (
        <div className="workflow-folder-status">
          <span>{discovery.source_status.status}</span>
          <span className="truncate">{discovery.source_status.path || 'No source folder'}</span>
        </div>
      ) : null}
      {statusMessages.map((message) => (
        <div key={`${message.code}-${message.message}`} className={`status-message status-${message.severity}`}>
          {message.message}
        </div>
      ))}
    </div>
  )
}

function PanelTitle({ stage }: { stage: WorkflowStageKey }) {
  const titles: Record<WorkflowStageKey, string> = {
    start: 'Item list',
    ocr: 'OCR tree',
    merge: 'Merge groups',
    rename: 'Rename preview',
  }
  return <h3 className="workflow-panel-title">{titles[stage]}</h3>
}

function LeftPanel({
  selectedStage,
  items,
  selectedSourceId,
  editablePlan,
  expandedGroupIds,
  selectedPlanItemId,
  selectedMergeResultId,
  dragState,
  dropTarget,
  mergeRows,
  renameRows,
  onSelectSource,
  onSelectPlanItem,
  onSelectMergeResult,
  onToggleGroup,
  onDragStart,
  onDropTargetChange,
  onDropPage,
  onDragEnd,
  workflowState,
  isStageRunning,
}: {
  selectedStage: WorkflowStageKey
  items: WorkflowSourceFile[]
  selectedSourceId: string | null
  editablePlan: EditableMergePlan | null
  expandedGroupIds: Set<string>
  selectedPlanItemId: string | null
  selectedMergeResultId: string | null
  dragState: DragPageState | null
  dropTarget: DropTarget | null
  mergeRows: WorkflowMergeResultItem[]
  renameRows: RenameRow[]
  onSelectSource: (id: string) => void
  onSelectPlanItem: (id: string) => void
  onSelectMergeResult: (id: string) => void
  onToggleGroup: (groupId: string) => void
  onDragStart: (page: EditableImagePage, groupId: string) => void
  onDropTargetChange: (target: DropTarget | null) => void
  onDropPage: (target: DropTarget) => void
  onDragEnd: () => void
  workflowState: WorkflowState | null
  isStageRunning: boolean
}) {
  if (selectedStage === 'start') {
    if (items.length === 0) {
      return <EmptyPanel text="No supported source files discovered." />
    }
    return (
      <div className="workflow-scroll-list">
        {items.map((item) => {
          const itemStatus = sourceOcrStatus(item, workflowState)
          const isRunningItem = itemStatus === 'running'
          const isDoneItem = itemStatus === 'done'
          const isFailedItem = itemStatus === 'failed'
          const isSelected = selectedSourceId === item.id && !isStageRunning

          return (
            <button
              type="button"
              key={item.id}
              aria-disabled={isStageRunning}
              tabIndex={isStageRunning ? -1 : 0}
              onClick={() => onSelectSource(item.id)}
              className={`workflow-row ${isStageRunning ? 'workflow-row-disabled' : ''} ${isSelected ? 'workflow-row-selected' : ''} ${isRunningItem ? 'workflow-row-active-ocr' : ''} ${isDoneItem ? 'workflow-row-done' : ''} ${isFailedItem ? 'workflow-row-failed' : ''} ${workflowState?.active_comparison?.left_source_id === item.id || workflowState?.active_comparison?.right_source_id === item.id ? 'workflow-row-active-comparison' : ''}`}
            >
              <span className="workflow-row-title">{item.display_name}</span>
              <span className="workflow-row-subtitle">
                {item.source_type.toUpperCase()} · {formatBytes(item.size_bytes)}
              </span>
              {itemStatus ? (
                <span
                  className={`workflow-row-process-status workflow-row-process-status-${itemStatus}`}
                  style={{ color: sourceOcrStatusColor(itemStatus) }}
                >
                  {itemStatus}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
    )
  }

  if (selectedStage === 'ocr') {
    if (!editablePlan) {
      return <EmptyPanel text="OCR rows will appear after OCR completes." />
    }
    return (
      <div className="workflow-scroll-list workflow-ocr-tree">
        {editablePlan.items.map((item, itemIndex) => (
          <OcrPlanItemRow
            key={item.id}
            item={item}
            itemIndex={itemIndex}
            expandedGroupIds={expandedGroupIds}
            selectedPlanItemId={selectedPlanItemId}
            dragState={dragState}
            dropTarget={dropTarget}
            onSelectPlanItem={onSelectPlanItem}
            onToggleGroup={onToggleGroup}
            onDragStart={onDragStart}
            onDropTargetChange={onDropTargetChange}
            onDropPage={onDropPage}
            onDragEnd={onDragEnd}
          />
        ))}
        <BetweenGroupDropZone
          index={editablePlan.items.length}
          dragState={dragState}
          dropTarget={dropTarget}
          onDropTargetChange={onDropTargetChange}
          onDropPage={onDropPage}
        />
      </div>
    )
  }

  if (selectedStage === 'merge') {
    if (workflowState?.merge_results_available && mergeRows.length > 0) {
      return (
        <div className="workflow-scroll-list">
          {mergeRows.map((row) => (
            <button
              type="button"
              key={row.id}
              disabled={isStageRunning || row.status !== 'ok'}
              onClick={() => onSelectMergeResult(row.id)}
              className={`workflow-row ${selectedMergeResultId === row.id ? 'workflow-row-selected' : ''} ${row.status === 'failed' ? 'workflow-row-failed' : 'workflow-row-done'}`}
            >
              <span className="workflow-row-title">{row.label}</span>
              <span className="workflow-row-subtitle">
                {row.status === 'ok'
                  ? `${row.output_pdf ?? 'PDF'} · ${row.output_markdown ?? 'Markdown'}`
                  : row.message ?? 'Merge failed'}
              </span>
              <span
                className={`workflow-row-process-status workflow-row-process-status-${row.status === 'ok' ? 'done' : 'failed'}`}
                style={{ color: mergeStatusColor(row.status === 'ok' ? 'done' : 'failed') }}
              >
                {row.status === 'ok' ? 'done' : 'failed'}
              </span>
            </button>
          ))}
        </div>
      )
    }

    return editablePlan ? (
      <div className="workflow-scroll-list">
        {editablePlan.items.map((item, index) => {
          const mergeItem = workflowState?.merge_items.find((candidate) => candidate.item_index === index + 1)
          const status = mergeItem?.status ?? 'pending'
          const label = isImageGroup(item) ? item.display_name : item.source_file_name
          const detail = isImageGroup(item) ? `${item.documents.length} image page(s)` : item.markdown_file
          return (
            <div key={item.id} className={`workflow-row-static workflow-merge-row-${status}`}>
              <span className="workflow-row-title">{label}</span>
              <span className="workflow-row-subtitle">{detail}</span>
              <span
                className={`workflow-row-process-status workflow-row-process-status-${status}`}
                style={{ color: mergeStatusColor(status) }}
              >
                {mergeStatusLabel(status)}
              </span>
              {mergeItem?.message ? <span className="workflow-row-subtitle">{mergeItem.message}</span> : null}
            </div>
          )
        })}
      </div>
    ) : (
      <EmptyPanel text="Merge groups will appear after OCR completes." />
    )
  }

  return renameRows.length > 0 ? (
    <div className="workflow-scroll-list">
      {renameRows.map((row) => (
        <div key={row.id} className="workflow-row-static">
          <span className="workflow-row-title">{row.current_name}</span>
          <span className="workflow-row-subtitle">{row.proposed_name}</span>
        </div>
      ))}
    </div>
  ) : (
    <EmptyPanel text="Rename proposals are unavailable until the simulated merge stage runs." />
  )
}

function OcrPlanItemRow({
  item,
  itemIndex,
  expandedGroupIds,
  selectedPlanItemId,
  dragState,
  dropTarget,
  onSelectPlanItem,
  onToggleGroup,
  onDragStart,
  onDropTargetChange,
  onDropPage,
  onDragEnd,
}: {
  item: EditablePlanItem
  itemIndex: number
  expandedGroupIds: Set<string>
  selectedPlanItemId: string | null
  dragState: DragPageState | null
  dropTarget: DropTarget | null
  onSelectPlanItem: (id: string) => void
  onToggleGroup: (groupId: string) => void
  onDragStart: (page: EditableImagePage, groupId: string) => void
  onDropTargetChange: (target: DropTarget | null) => void
  onDropPage: (target: DropTarget) => void
  onDragEnd: () => void
}) {
  if (!isImageGroup(item)) {
    const isSelected = selectedPlanItemId === item.id
    return (
      <>
        <BetweenGroupDropZone
          index={itemIndex}
          dragState={dragState}
          dropTarget={dropTarget}
          onDropTargetChange={onDropTargetChange}
          onDropPage={onDropPage}
        />
        <button
          type="button"
          className={`workflow-ocr-row workflow-ocr-pdf-row ${isSelected ? 'workflow-ocr-row-selected' : ''}`}
          onClick={() => onSelectPlanItem(item.id)}
        >
          <span className="workflow-row-title">{item.source_file_name}</span>
          <span className="workflow-row-subtitle">PDF · {item.markdown_file}</span>
        </button>
      </>
    )
  }

  const isExpanded = expandedGroupIds.has(item.id)
  return (
    <>
      <BetweenGroupDropZone
        index={itemIndex}
        dragState={dragState}
        dropTarget={dropTarget}
        onDropTargetChange={onDropTargetChange}
        onDropPage={onDropPage}
      />
      <div className="workflow-ocr-group">
        <button
          type="button"
          className="workflow-ocr-group-row"
          onClick={() => onToggleGroup(item.id)}
          aria-expanded={isExpanded}
        >
          <span className="workflow-ocr-expander">{isExpanded ? '-' : '+'}</span>
          <span className="workflow-row-title">{item.display_name}</span>
          <span className="workflow-row-subtitle">{item.documents.length} image page(s)</span>
        </button>
        {isExpanded ? (
          <div className="workflow-ocr-group-children">
            {item.documents.map((page, pageIndex) => (
              <div key={page.id}>
                <InsideGroupDropZone
                  groupId={item.id}
                  index={pageIndex}
                  dragState={dragState}
                  dropTarget={dropTarget}
                  onDropTargetChange={onDropTargetChange}
                  onDropPage={onDropPage}
                />
                <button
                  type="button"
                  draggable
                  className={`workflow-ocr-row workflow-ocr-page-row ${selectedPlanItemId === page.id ? 'workflow-ocr-row-selected' : ''} ${dragState?.pageId === page.id ? 'workflow-ocr-row-dragging' : ''}`}
                  onClick={() => onSelectPlanItem(page.id)}
                  onDragStart={(event) => {
                    event.dataTransfer.effectAllowed = 'move'
                    event.dataTransfer.setData('text/plain', page.id)
                    onDragStart(page, item.id)
                  }}
                  onDragEnd={onDragEnd}
                >
                  <span className="workflow-ocr-page-copy">
                    <span className="workflow-row-subtitle">Image - {page.source_file_name}</span>
                  </span>
                </button>
              </div>
            ))}
            <InsideGroupDropZone
              groupId={item.id}
              index={item.documents.length}
              dragState={dragState}
              dropTarget={dropTarget}
              onDropTargetChange={onDropTargetChange}
              onDropPage={onDropPage}
            />
          </div>
        ) : null}
      </div>
    </>
  )
}

function InsideGroupDropZone({
  groupId,
  index,
  dragState,
  dropTarget,
  onDropTargetChange,
  onDropPage,
}: {
  groupId: string
  index: number
  dragState: DragPageState | null
  dropTarget: DropTarget | null
  onDropTargetChange: (target: DropTarget | null) => void
  onDropPage: (target: DropTarget) => void
}) {
  const target: DropTarget = { kind: 'inside-group', groupId, index }
  const isActive = dropTarget?.kind === 'inside-group' && dropTarget.groupId === groupId && dropTarget.index === index
  return (
    <div
      className={`workflow-ocr-drop-zone workflow-ocr-drop-zone-inside ${isActive ? 'workflow-ocr-drop-zone-active' : ''}`}
      onDragOver={(event) => {
        if (!dragState) {
          return
        }
        event.preventDefault()
        onDropTargetChange(target)
      }}
      onDragLeave={() => onDropTargetChange(null)}
      onDrop={(event) => {
        event.preventDefault()
        if (dragState) {
          onDropPage(target)
        }
      }}
    />
  )
}

function BetweenGroupDropZone({
  index,
  dragState,
  dropTarget,
  onDropTargetChange,
  onDropPage,
}: {
  index: number
  dragState: DragPageState | null
  dropTarget: DropTarget | null
  onDropTargetChange: (target: DropTarget | null) => void
  onDropPage: (target: DropTarget) => void
}) {
  const target: DropTarget = { kind: 'between-groups', index }
  const isActive = dropTarget?.kind === 'between-groups' && dropTarget.index === index
  return (
    <div
      className={`workflow-ocr-drop-zone workflow-ocr-drop-zone-between ${isActive ? 'workflow-ocr-drop-zone-active' : ''}`}
      onDragOver={(event) => {
        if (!dragState) {
          return
        }
        event.preventDefault()
        onDropTargetChange(target)
      }}
      onDragLeave={() => onDropTargetChange(null)}
      onDrop={(event) => {
        event.preventDefault()
        if (dragState) {
          onDropPage(target)
        }
      }}
    />
  )
}

function MiddlePanel({
  selectedStage,
  selectedSource,
  selectedPlanItem,
  selectedMergeResult,
}: {
  selectedStage: WorkflowStageKey
  selectedSource: WorkflowSourceFile | null
  selectedPlanItem: EditablePlanDocument | null
  selectedMergeResult: WorkflowMergeResultItem | null
}) {
  if (selectedStage === 'ocr') {
    if (!selectedPlanItem) {
      return <EmptyPanel text="Select an OCR item to preview its generated artifact." />
    }
    const previewUrl = buildOcrArtifactPreviewUrl(selectedPlanItem)
    if (selectedPlanItem.file_type === 'image') {
      return (
        <div className="workflow-image-frame">
          <img src={previewUrl} alt={selectedPlanItem.source_file_name} />
        </div>
      )
    }
    return <PdfPreview fileUrl={previewUrl} />
  }

  if (selectedStage === 'merge') {
    if (!selectedMergeResult) {
      return <EmptyPanel text="Select a merge result to preview its PDF." />
    }
    if (selectedMergeResult.status !== 'ok') {
      return <EmptyPanel text={selectedMergeResult.message ?? 'This merge result failed.'} />
    }
    return <PdfPreview fileUrl={buildMergeResultPdfPreviewUrl(selectedMergeResult)} />
  }

  if (selectedStage !== 'start') {
    return (
      <div className="workflow-preview-empty">
        <span>{selectedStage.toUpperCase()} metadata is simulated in this phase.</span>
      </div>
    )
  }

  if (!selectedSource) {
    return <EmptyPanel text="Select Start to discover source files." />
  }

  const previewUrl = buildSourcePreviewUrl(selectedSource)
  if (selectedSource.source_type === 'image' && previewUrl) {
    return (
      <div className="workflow-image-frame">
        <img src={previewUrl} alt={selectedSource.display_name} />
      </div>
    )
  }

  if (selectedSource.source_type === 'pdf' && previewUrl) {
    return <PdfPreview fileUrl={previewUrl} />
  }

  return (
    <div className="workflow-metadata">
      <span className="workflow-row-title">{selectedSource.display_name}</span>
      <span>Preview is unavailable for this source.</span>
      <span>{selectedSource.absolute_path}</span>
      <span>{formatBytes(selectedSource.size_bytes)}</span>
    </div>
  )
}

function PdfPreview({
  fileUrl,
}: {
  fileUrl: string
}) {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const panStateRef = useRef<PdfPanState | null>(null)
  const [numPages, setNumPages] = useState<number | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [viewerSize, setViewerSize] = useState<{ width: number; height: number } | null>(null)
  const [zoomMode, setZoomMode] = useState<PdfZoomMode>('fit-width')
  const [customZoom, setCustomZoom] = useState(100)
  const [isPanning, setIsPanning] = useState(false)

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) {
      return
    }

    const updateSize = (width: number, height: number) => {
      setViewerSize({
        width: Math.max(160, Math.floor(width)),
        height: Math.max(160, Math.floor(height)),
      })
    }

    updateSize(viewer.clientWidth, viewer.clientHeight)
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect
      updateSize(rect?.width ?? viewer.clientWidth, rect?.height ?? viewer.clientHeight)
    })
    observer.observe(viewer)

    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    setNumPages(null)
    setPageNumber(1)
  }, [fileUrl])

  function handleLoadSuccess({ numPages: nextNumPages }: { numPages: number }) {
    setNumPages(nextNumPages)
    setPageNumber((currentPage) => Math.min(currentPage, nextNumPages))
  }

  function handlePanStart(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) {
      return
    }

    const viewer = event.currentTarget
    panStateRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: viewer.scrollLeft,
      scrollTop: viewer.scrollTop,
    }
    viewer.setPointerCapture(event.pointerId)
    setIsPanning(true)
    event.preventDefault()
  }

  function handlePanMove(event: ReactPointerEvent<HTMLDivElement>) {
    const panState = panStateRef.current
    if (!panState || panState.pointerId !== event.pointerId) {
      return
    }

    const viewer = event.currentTarget
    viewer.scrollLeft = panState.scrollLeft - (event.clientX - panState.startX)
    viewer.scrollTop = panState.scrollTop - (event.clientY - panState.startY)
  }

  function handlePanEnd(event: ReactPointerEvent<HTMLDivElement>) {
    const panState = panStateRef.current
    if (!panState || panState.pointerId !== event.pointerId) {
      return
    }

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    panStateRef.current = null
    setIsPanning(false)
  }

  const canGoPrevious = pageNumber > 1
  const canGoNext = numPages !== null && pageNumber < numPages
  const actualSizeScale = PDF_CSS_PIXELS_PER_POINT
  const customScale = actualSizeScale * (customZoom / 100)

  function renderPage() {
    if (viewerSize === null) {
      return <span className="workflow-pdf-status">Preparing PDF preview...</span>
    }

    const commonPageProps = {
      pageNumber,
      renderAnnotationLayer: false,
      renderTextLayer: false,
    }

    if (zoomMode === 'fit-height') {
      return <Page {...commonPageProps} height={viewerSize.height} />
    }
    if (zoomMode === 'actual-size') {
      return <Page {...commonPageProps} scale={actualSizeScale} />
    }
    if (zoomMode === 'custom') {
      return <Page {...commonPageProps} scale={customScale} />
    }
    return <Page {...commonPageProps} width={viewerSize.width} />
  }

  return (
    <div className="workflow-pdf-frame">
      <div className="workflow-pdf-toolbar">
        <div className="workflow-pdf-controls">
          <button
            type="button"
            className="btn-ghost"
            disabled={!canGoPrevious}
            onClick={() => setPageNumber((currentPage) => Math.max(1, currentPage - 1))}
          >
            Previous
          </button>
          <span>
            Page {pageNumber} of {numPages ?? '-'}
          </span>
          <button
            type="button"
            className="btn-ghost"
            disabled={!canGoNext}
            onClick={() =>
              setPageNumber((currentPage) =>
                numPages === null ? currentPage : Math.min(numPages, currentPage + 1),
              )
            }
          >
            Next
          </button>
        </div>
        <div className="workflow-pdf-controls">
          <label className="workflow-pdf-zoom-label" htmlFor="workflow-pdf-zoom-mode">
            Zoom
          </label>
          <select
            id="workflow-pdf-zoom-mode"
            className="workflow-pdf-select"
            value={zoomMode}
            onChange={(event) => setZoomMode(event.target.value as PdfZoomMode)}
          >
            <option value="fit-width">Fit width</option>
            <option value="fit-height">Fit height</option>
            <option value="actual-size">100%</option>
            <option value="custom">Custom</option>
          </select>
          {zoomMode === 'custom' ? (
            <label className="workflow-pdf-custom-zoom">
              <input
                type="number"
                min="25"
                max="300"
                step="5"
                value={customZoom}
                onChange={(event) => {
                  const nextZoom = Number(event.target.value)
                  if (Number.isFinite(nextZoom)) {
                    setCustomZoom(Math.min(300, Math.max(25, nextZoom)))
                  }
                }}
              />
              <span>%</span>
            </label>
          ) : null}
        </div>
      </div>
      <div
        className={`workflow-pdf-viewer${isPanning ? ' workflow-pdf-viewer-panning' : ''}`}
        ref={viewerRef}
        onPointerDown={handlePanStart}
        onPointerMove={handlePanMove}
        onPointerUp={handlePanEnd}
        onPointerCancel={handlePanEnd}
      >
        <Document
          file={fileUrl}
          loading={<span className="workflow-pdf-status">Loading PDF...</span>}
          error={<span className="workflow-pdf-status">PDF preview could not be loaded.</span>}
          onLoadSuccess={handleLoadSuccess}
        >
          {renderPage()}
        </Document>
      </div>
    </div>
  )
}

function RightPanel({
  selectedStage,
  selectedSource,
  selectedPlanItem,
  selectedMergeResult,
  markdownPreview,
  markdownPreviewStatus,
  markdownViewMode,
}: {
  selectedStage: WorkflowStageKey
  selectedSource: WorkflowSourceFile | null
  selectedPlanItem: EditablePlanDocument | null
  selectedMergeResult: WorkflowMergeResultItem | null
  markdownPreview: MarkdownPreviewResponse | null
  markdownPreviewStatus: MarkdownPreviewStatus
  markdownViewMode: MarkdownViewMode
}) {
  if (selectedStage === 'start') {
    return <EmptyPanel text="Markdown preview is unavailable before OCR." />
  }

  if (selectedStage === 'ocr') {
    if (!selectedPlanItem) {
      return <EmptyPanel text="Select an OCR item to preview its Markdown." />
    }
    if (markdownPreviewStatus === 'loading') {
      return <EmptyPanel text="Loading Markdown preview..." />
    }
    if (markdownPreviewStatus === 'error') {
      return <EmptyPanel text="Markdown preview could not be loaded." />
    }
    const content = markdownPreview?.content || 'Markdown preview is empty.'
    if (markdownViewMode === 'code') {
      return (
        <div className="workflow-markdown-preview workflow-markdown-code-view">
          <SyntaxHighlighter
            language="markdown"
            style={oneDark}
            customStyle={{ margin: 0, background: 'transparent', padding: 0 }}
            codeTagProps={{ className: 'workflow-markdown-code' }}
            wrapLongLines
          >
            {content}
          </SyntaxHighlighter>
        </div>
      )
    }
    return (
      <MathJaxContext>
        <MathJax dynamic className="workflow-markdown-preview workflow-markdown-rendered">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, [rehypeSanitize, MARKDOWN_SANITIZE_SCHEMA], rehypeMathjax]}
          >
            {content}
          </ReactMarkdown>
        </MathJax>
      </MathJaxContext>
    )
  }

  if (selectedStage === 'merge') {
    if (!selectedMergeResult) {
      return <EmptyPanel text="Select a merge result to preview its Markdown." />
    }
    if (selectedMergeResult.status !== 'ok') {
      return <EmptyPanel text={selectedMergeResult.message ?? 'This merge result failed.'} />
    }
    if (markdownPreviewStatus === 'loading') {
      return <EmptyPanel text="Loading Markdown preview..." />
    }
    if (markdownPreviewStatus === 'error') {
      return <EmptyPanel text="Markdown preview could not be loaded." />
    }
    const content = markdownPreview?.content || 'Markdown preview is empty.'
    if (markdownViewMode === 'code') {
      return (
        <div className="workflow-markdown-preview workflow-markdown-code-view">
          <SyntaxHighlighter
            language="markdown"
            style={oneDark}
            customStyle={{ margin: 0, background: 'transparent', padding: 0 }}
            codeTagProps={{ className: 'workflow-markdown-code' }}
            wrapLongLines
          >
            {content}
          </SyntaxHighlighter>
        </div>
      )
    }
    return (
      <MathJaxContext>
        <MathJax dynamic className="workflow-markdown-preview workflow-markdown-rendered">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, [rehypeSanitize, MARKDOWN_SANITIZE_SCHEMA], rehypeMathjax]}
          >
            {content}
          </ReactMarkdown>
        </MathJax>
      </MathJaxContext>
    )
  }

  const name = selectedSource?.display_name ?? 'selected source'
  return (
    <div className="workflow-markdown-preview workflow-markdown-placeholder">
      <span># {selectedStage.toUpperCase()} placeholder</span>
      <span>Source: {name}</span>
      <span>Generated content will appear here when this stage is implemented.</span>
    </div>
  )
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <div className="workflow-preview-empty">
      <span>{text}</span>
    </div>
  )
}