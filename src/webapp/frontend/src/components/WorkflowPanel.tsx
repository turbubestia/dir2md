import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { buildSourcePreviewUrl, startWorkflowDiscovery } from '../api'
import type {
  MergeRow,
  OcrTreeRow,
  RenameRow,
  WorkflowDiscoveryResponse,
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
type PdfZoomMode = 'fit-width' | 'fit-height' | 'actual-size' | 'custom'
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
  ocrRows,
  mergeRows,
  renameRows,
}: {
  stage: WorkflowStageKey
  hasDiscovery: boolean
  metrics: typeof EMPTY_METRICS
  ocrRows: OcrTreeRow[]
  mergeRows: MergeRow[]
  renameRows: RenameRow[]
}): StageStatusLine[] {
  if (stage === 'start') {
    return [
      { label: 'PDF Files', value: displayCount(hasDiscovery, metrics.pdf_count) },
      { label: 'Image Files', value: displayCount(hasDiscovery, metrics.image_count) },
    ]
  }

  if (stage === 'ocr') {
    const markdownCount = ocrRows.length > 0 ? ocrRows.length : metrics.total_count
    const imageGroups = metrics.image_count > 0 ? Math.ceil(metrics.image_count / 3) : 0
    return [
      { label: 'Markdown Files', value: displayCount(hasDiscovery, markdownCount) },
      { label: 'PDF Documents', value: displayCount(hasDiscovery, metrics.pdf_count) },
      { label: 'Image Groups', value: displayCount(hasDiscovery, imageGroups) },
    ]
  }

  if (stage === 'merge') {
    return [{ label: 'Documents', value: mergeRows.length > 0 ? String(mergeRows.length) : '-' }]
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

export default function WorkflowPanel() {
  const [selectedStage, setSelectedStage] = useState<WorkflowStageKey>('start')
  const [progressStage, setProgressStage] = useState<WorkflowStageKey>('start')
  const [stageStates, setStageStates] =
    useState<Record<WorkflowStageKey, WorkflowStageState>>(INITIAL_STAGE_STATES)
  const [discovery, setDiscovery] = useState<WorkflowDiscoveryResponse | null>(null)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [messages, setMessages] = useState<WorkflowStatusMessage[]>([])
  const [ocrRows, setOcrRows] = useState<OcrTreeRow[]>([])
  const [mergeRows, setMergeRows] = useState<MergeRow[]>([])
  const [renameRows, setRenameRows] = useState<RenameRow[]>([])
  const [timerId, setTimerId] = useState<number | null>(null)

  useEffect(() => {
    return () => {
      if (timerId !== null) {
        window.clearTimeout(timerId)
      }
    }
  }, [timerId])

  const items = discovery?.items ?? []
  const selectedSource =
    items.find((item) => item.id === selectedSourceId) ?? items[0] ?? null
  const metrics = discovery?.metrics ?? EMPTY_METRICS
  const hasDiscovery = discovery !== null

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
    setOcrRows([])
    setMergeRows([])
    setRenameRows([])
    setSelectedSourceId(null)
    setMessages([{ severity: 'info', code: 'start_running', message: 'Reading configured source folder.' }])

    try {
      const response = await startWorkflowDiscovery()
      setDiscovery(response)
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

  function runSimulatedStage(stage: Exclude<WorkflowStageKey, 'start'>) {
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
      if (stage === 'ocr') {
        setOcrRows(
          items.map((item) => ({
            id: `ocr-${item.id}`,
            label: `${item.display_name}.md`,
            source_id: item.id,
            status: 'simulated',
          })),
        )
        setStageStates((current) => ({ ...current, ocr: 'complete', merge: 'enabled' }))
      }
      if (stage === 'merge') {
        setMergeRows([
          {
            id: 'merge-preview',
            title: 'Simulated document group',
            item_count: items.length,
            status: 'simulated',
          },
        ])
        setStageStates((current) => ({ ...current, merge: 'complete', rename: 'enabled' }))
      }
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

  function handleStageClick(stage: WorkflowStageKey) {
    setProgressStage(stage)
    if (stage === 'start') {
      void runStart()
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
            style={{ width: `${stageProgressPercent(progressStage)}%` }}
            aria-hidden="true"
          />
          <div className="workflow-stage-grid">
            {STAGES.map((stage, index) => {
              const state = selectedStage === stage.key ? 'selected' : stageStates[stage.key]
              const nextStage = STAGES[index + 1]?.key
              const outgoingState = nextStage ? connectorState(stage.key, nextStage, stageStates) : 'none'
              const lines = stageStatusLines({
                stage: stage.key,
                hasDiscovery,
                metrics,
                ocrRows,
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
                    onClick={() => handleStageClick(stage.key)}
                    className={`workflow-stage workflow-stage-${state} ${stageButtonFillClass(state)}`}
                    aria-pressed={selectedStage === stage.key}
                    aria-disabled={stageStates[stage.key] === 'unavailable'}
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
            ocrRows={ocrRows}
            mergeRows={mergeRows}
            renameRows={renameRows}
            onSelectSource={setSelectedSourceId}
          />
        </section>
        <section className="workflow-panel workflow-preview-panel">
          <h3 className="workflow-panel-title">Document preview</h3>
          <MiddlePanel selectedStage={selectedStage} selectedSource={selectedSource} />
        </section>
        <section className="workflow-panel workflow-preview-panel">
          <div className="workflow-panel-heading">
            <h3 className="workflow-panel-title">Markdown</h3>
            <span>Code <strong>Preview</strong></span>
          </div>
          <RightPanel selectedStage={selectedStage} selectedSource={selectedSource} />
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
  ocrRows,
  mergeRows,
  renameRows,
  onSelectSource,
}: {
  selectedStage: WorkflowStageKey
  items: WorkflowSourceFile[]
  selectedSourceId: string | null
  ocrRows: OcrTreeRow[]
  mergeRows: MergeRow[]
  renameRows: RenameRow[]
  onSelectSource: (id: string) => void
}) {
  if (selectedStage === 'start') {
    if (items.length === 0) {
      return <EmptyPanel text="No supported source files discovered." />
    }
    return (
      <div className="workflow-scroll-list">
        {items.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelectSource(item.id)}
            className={`workflow-row ${selectedSourceId === item.id ? 'workflow-row-selected' : ''}`}
          >
            <span className="workflow-row-title">{item.display_name}</span>
            <span className="workflow-row-subtitle">
              {item.source_type.toUpperCase()} · {formatBytes(item.size_bytes)}
            </span>
          </button>
        ))}
      </div>
    )
  }

  if (selectedStage === 'ocr') {
    return ocrRows.length > 0 ? (
      <div className="workflow-scroll-list">
        {ocrRows.map((row) => (
          <div key={row.id} className="workflow-tree-row">
            <span className="workflow-tree-branch" />
            <span className="workflow-row-title">{row.label}</span>
            <span className="workflow-row-subtitle">OCR placeholder</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyPanel text="OCR rows will appear after the placeholder stage runs." />
    )
  }

  if (selectedStage === 'merge') {
    return mergeRows.length > 0 ? (
      <div className="workflow-scroll-list">
        {mergeRows.map((row) => (
          <div key={row.id} className="workflow-row-static">
            <span className="workflow-row-title">{row.title}</span>
            <span className="workflow-row-subtitle">{row.item_count} item(s), simulated merge</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyPanel text="Merge groups are frontend-only placeholders for now." />
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

function MiddlePanel({
  selectedStage,
  selectedSource,
}: {
  selectedStage: WorkflowStageKey
  selectedSource: WorkflowSourceFile | null
}) {
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
}: {
  selectedStage: WorkflowStageKey
  selectedSource: WorkflowSourceFile | null
}) {
  if (selectedStage === 'start') {
    return <EmptyPanel text="Markdown preview is unavailable before OCR." />
  }

  const name = selectedSource?.display_name ?? 'selected source'
  return (
    <div className="workflow-markdown-preview">
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