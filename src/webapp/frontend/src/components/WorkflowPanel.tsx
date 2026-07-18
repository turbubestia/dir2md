import { useEffect, useState } from 'react'
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

const STAGES: { key: WorkflowStageKey; label: string }[] = [
  { key: 'start', label: 'Start' },
  { key: 'ocr', label: 'OCR' },
  { key: 'merge', label: 'Merge' },
  { key: 'rename', label: 'Rename' },
]

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

export default function WorkflowPanel() {
  const [selectedStage, setSelectedStage] = useState<WorkflowStageKey>('start')
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

  function clearPendingTimer() {
    if (timerId !== null) {
      window.clearTimeout(timerId)
      setTimerId(null)
    }
  }

  async function runStart() {
    clearPendingTimer()
    setSelectedStage('start')
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
    if (stage === 'start') {
      void runStart()
      return
    }
    runSimulatedStage(stage)
  }

  return (
    <section className="workflow-root panel">
      <div className="workflow-toolbar">
        <div className="workflow-stage-strip">
          {STAGES.map((stage, index) => {
            const state = selectedStage === stage.key ? 'selected' : stageStates[stage.key]
            return (
              <div key={stage.key} className="workflow-stage-slot">
                <button
                  type="button"
                  onClick={() => handleStageClick(stage.key)}
                  className={`workflow-stage workflow-stage-${state}`}
                  aria-pressed={selectedStage === stage.key}
                  aria-disabled={stageStates[stage.key] === 'unavailable'}
                >
                  <span className="workflow-stage-index">{index + 1}</span>
                  <span>{stage.label}</span>
                </button>
                {index < STAGES.length - 1 ? (
                  <div
                    className={`workflow-connector ${stageStates[stage.key] === 'complete' ? 'workflow-connector-complete' : ''}`}
                  />
                ) : null}
              </div>
            )
          })}
        </div>
        <div className="workflow-metrics">
          <div className="metric-cell">
            <span>PDF</span>
            <strong>{metrics.pdf_count}</strong>
          </div>
          <div className="metric-cell">
            <span>Images</span>
            <strong>{metrics.image_count}</strong>
          </div>
          <div className="metric-cell">
            <span>Total</span>
            <strong>{metrics.total_count}</strong>
          </div>
          <div className="metric-cell metric-cell-muted">
            <span>Downstream</span>
            <strong>{ocrRows.length || mergeRows.length || renameRows.length ? 'Simulated' : 'Pending'}</strong>
          </div>
        </div>
        <StatusArea messages={messages} discovery={discovery} />
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
          <h3 className="workflow-panel-title">Source preview</h3>
          <MiddlePanel selectedStage={selectedStage} selectedSource={selectedSource} />
        </section>
        <section className="workflow-panel workflow-preview-panel">
          <h3 className="workflow-panel-title">Markdown preview</h3>
          <RightPanel selectedStage={selectedStage} selectedSource={selectedSource} />
        </section>
      </div>
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
    start: 'Source files',
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
            <span className="workflow-row-path">{item.absolute_path}</span>
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

  return (
    <div className="workflow-metadata">
      <span className="workflow-row-title">{selectedSource.display_name}</span>
      <span>PDF preview is metadata-only in this phase.</span>
      <span>{selectedSource.absolute_path}</span>
      <span>{formatBytes(selectedSource.size_bytes)}</span>
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