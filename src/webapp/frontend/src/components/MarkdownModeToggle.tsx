import type { MarkdownViewMode } from './MarkdownViewer'

interface MarkdownModeToggleProps {
  mode: MarkdownViewMode
  onModeChange: (mode: MarkdownViewMode) => void
  label?: string
  className?: string
}

export default function MarkdownModeToggle({
  mode,
  onModeChange,
  label = 'Markdown view mode',
  className = '',
}: MarkdownModeToggleProps) {
  return (
    <div className={`flex items-center gap-1 ${className}`} role="group" aria-label={label}>
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
  )
}
