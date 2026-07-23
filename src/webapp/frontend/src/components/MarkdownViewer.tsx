import { MathJax, MathJaxContext } from 'better-react-mathjax'
import ReactMarkdown from 'react-markdown'
import rehypeMathjax from 'rehype-mathjax/svg'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

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

export type MarkdownViewMode = 'code' | 'preview'

interface MarkdownViewerProps {
  content: string
  mode: MarkdownViewMode
  className?: string
  onModeChange?: (mode: MarkdownViewMode) => void
}

export default function MarkdownViewer({
  content,
  mode,
  className = '',
  onModeChange,
}: MarkdownViewerProps) {
  return (
    <div className={`flex flex-col h-full ${className}`}>
      {onModeChange && (
        <div className="flex items-center justify-end gap-1 mb-1" role="group" aria-label="Markdown view mode">
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
      )}
      <div className="flex-1 min-h-0 overflow-auto">
        {mode === 'code' ? (
          <div className="h-full p-2 workflow-markdown-preview workflow-markdown-code-view">
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
        ) : (
          <MathJaxContext>
            <MathJax dynamic className="h-full p-2 workflow-markdown-preview workflow-markdown-rendered">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeRaw, [rehypeSanitize, MARKDOWN_SANITIZE_SCHEMA], rehypeMathjax]}
              >
                {content}
              </ReactMarkdown>
            </MathJax>
          </MathJaxContext>
        )}
      </div>
    </div>
  )
}
