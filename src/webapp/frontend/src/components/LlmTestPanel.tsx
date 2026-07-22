import { useEffect, useRef, useState } from 'react'
import {
  WORKFLOW_EVENTS_URL,
  fetchLlmTestPrompt,
  fetchWorkflowState,
  saveLlmTestPrompt,
  startLlmTest,
} from '../api'
import type { LlmTestResult, WorkflowState } from '../types'
import MarkdownViewer, { type MarkdownViewMode } from './MarkdownViewer'

const PROMPT_PATHS = {
  system: 'data/temp/llm_test_system.md',
  user: 'data/temp/llm_test_user.md',
  assistant: 'data/temp/llm_test_assistant.md',
}

type PromptKey = keyof typeof PROMPT_PATHS

interface EditorState {
  text: string
  mode: MarkdownViewMode
}

function useDebouncedPromptSave(key: PromptKey, text: string, onError: (message: string) => void) {
  const initialised = useRef(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    if (!initialised.current) {
      initialised.current = true
      return
    }

    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
    }

    timerRef.current = window.setTimeout(() => {
      void saveLlmTestPrompt(key, text).catch((error: unknown) => {
        const message = error instanceof Error ? error.message : `Failed to save ${key} prompt`
        onError(message)
      })
    }, 500)

    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current)
      }
    }
  }, [key, text, onError])
}

function PromptEditor({
  title,
  value,
  onChange,
  mode,
  onModeChange,
  className = '',
  actions,
}: {
  title: string
  value: string
  onChange: (value: string) => void
  mode: MarkdownViewMode
  onModeChange: (mode: MarkdownViewMode) => void
  className?: string
  actions?: React.ReactNode
}) {
  return (
    <div className={`flex flex-col min-h-0 ${className}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
          {title}
        </span>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1" role="group" aria-label={`${title} view mode`}>
            {(['code', 'preview'] as const).map((candidate) => (
              <button
                key={candidate}
                type="button"
                className={`text-xs px-2 py-0.5 rounded border ${
                  mode === candidate
                    ? 'bg-shell-border border-shell-border text-shell-text'
                    : 'border-shell-border text-shell-muted hover:text-shell-text hover:bg-shell-panel'
                }`}
                aria-pressed={mode === candidate}
                onClick={() => onModeChange(candidate)}
              >
                {candidate === 'code' ? 'Code' : 'Preview'}
              </button>
            ))}
          </div>
          {actions}
        </div>
      </div>
      {mode === 'code' ? (
        <textarea
          className="flex-1 min-h-0 input-field font-mono text-xs resize-none p-2 leading-relaxed"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
        />
      ) : (
        <MarkdownViewer
          content={value}
          mode="preview"
          className="flex-1 min-h-0 border border-shell-border rounded bg-shell-panel/50"
        />
      )}
    </div>
  )
}

export default function LlmTestPanel() {
  const [editors, setEditors] = useState<Record<PromptKey, EditorState>>({
    system: { text: '', mode: 'code' },
    user: { text: '', mode: 'code' },
    assistant: { text: '', mode: 'code' },
  })
  const [view, setView] = useState<'edit' | 'response'>('edit')
  const [result, setResult] = useState<LlmTestResult | null>(null)
  const [status, setStatus] = useState<WorkflowState['llm_test_status']>('idle')
  const [error, setError] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)
  const hasLoaded = useRef(false)

  useEffect(() => {
    if (hasLoaded.current) {
      return
    }
    hasLoaded.current = true

    const load = async () => {
      try {
        const [system, user, assistant, state] = await Promise.all([
          fetchLlmTestPrompt('system'),
          fetchLlmTestPrompt('user'),
          fetchLlmTestPrompt('assistant'),
          fetchWorkflowState().catch(() => null),
        ])
        setEditors((prev) => ({
          system: { ...prev.system, text: system },
          user: { ...prev.user, text: user },
          assistant: { ...prev.assistant, text: assistant },
        }))
        if (state?.llm_test_result) {
          setResult(state.llm_test_result)
        }
        if (state?.llm_test_status) {
          setStatus(state.llm_test_status)
        }
      } catch (error_) {
        const message = error_ instanceof Error ? error_.message : 'Failed to load LLM test panel'
        setError(message)
      }
    }

    void load()
  }, [])

  useEffect(() => {
    const eventSource = new EventSource(WORKFLOW_EVENTS_URL)

    const handleState = (event: MessageEvent) => {
      try {
        const state = JSON.parse(event.data) as WorkflowState
        if (state.llm_test_status) {
          setStatus(state.llm_test_status)
        }
        if (state.llm_test_result) {
          setResult(state.llm_test_result)
        }
      } catch {
        // ignore malformed events
      }
    }

    eventSource.addEventListener('workflow_state', handleState)
    return () => {
      eventSource.removeEventListener('workflow_state', handleState)
      eventSource.close()
    }
  }, [])

  useDebouncedPromptSave('system', editors.system.text, setError)
  useDebouncedPromptSave('user', editors.user.text, setError)
  useDebouncedPromptSave('assistant', editors.assistant.text, setError)

  const updateEditor = (key: PromptKey, patch: Partial<EditorState>) => {
    setEditors((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }))
    setError('')
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    setResult(null)
    setView('response')

    try {
      await startLlmTest({
        system_path: PROMPT_PATHS.system,
        user_path: PROMPT_PATHS.user,
        assistant_path: PROMPT_PATHS.assistant,
      })
    } catch (error_) {
      const message = error_ instanceof Error ? error_.message : 'LLM test failed to start'
      setError(message)
      setSubmitting(false)
    }
  }

  if (view === 'response') {
    return (
      <div className="h-full flex flex-col p-3 space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
            LLM test response
          </h3>
          <button
            type="button"
            onClick={() => setView('edit')}
            className="btn-ghost text-xs"
            disabled={status === 'running'}
          >
            Back
          </button>
        </div>
        {error && (
          <div className="rounded bg-red-900/30 border border-red-800 px-3 py-1.5 text-sm text-red-300">
            {error}
          </div>
        )}
        {result?.error && (
          <div className="rounded bg-red-900/30 border border-red-800 px-3 py-1.5 text-sm text-red-300">
            {result.error.message}
          </div>
        )}
        {status === 'running' && (
          <div className="text-sm text-shell-muted">Running LLM test...</div>
        )}
        <div className="flex-1 min-h-0 border border-shell-border rounded bg-shell-panel/50">
          <MarkdownViewer
            content={result?.text ?? ''}
            mode="preview"
            className="h-full p-2"
          />
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
          LLM test prompts
        </h3>
      </div>
      {error && (
        <div className="rounded bg-red-900/30 border border-red-800 px-3 py-1.5 text-sm text-red-300">
          {error}
        </div>
      )}
      <PromptEditor
        title="System"
        value={editors.system.text}
        onChange={(text) => updateEditor('system', { text })}
        mode={editors.system.mode}
        onModeChange={(mode) => updateEditor('system', { mode })}
        className="flex-[3] min-h-0"
        actions={
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="btn-primary text-xs px-3 py-1"
          >
            {submitting || status === 'running' ? 'Running...' : 'Submit'}
          </button>
        }
      />
      <PromptEditor
        title="User"
        value={editors.user.text}
        onChange={(text) => updateEditor('user', { text })}
        mode={editors.user.mode}
        onModeChange={(mode) => updateEditor('user', { mode })}
        className="flex-[6] min-h-0"
      />
      <PromptEditor
        title="Assistant (optional)"
        value={editors.assistant.text}
        onChange={(text) => updateEditor('assistant', { text })}
        mode={editors.assistant.mode}
        onModeChange={(mode) => updateEditor('assistant', { mode })}
        className="flex-[1] min-h-0"
      />
    </div>
  )
}
