import { useState } from 'react'
import SettingsForm from './SettingsForm'

type Section = 'workflow' | 'settings'

const WORKFLOW_PANELS = [
  'Source list',
  'Source preview',
  'batch_mrg.json',
  'Merge-document preview',
  'Output list',
]

export default function WorkspaceShell() {
  const [activeSection, setActiveSection] = useState<Section>('workflow')
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-shell-border">
        <h1 className="text-shell-text font-semibold tracking-wide">dir2md</h1>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        <button
          onClick={() => setActiveSection('workflow')}
          className={`w-full text-left px-3 py-2 rounded text-sm font-medium transition-colors ${
            activeSection === 'workflow'
              ? 'bg-shell-border text-shell-text'
              : 'text-shell-muted hover:text-shell-text hover:bg-shell-panel'
          }`}
        >
          Workflow
        </button>
        <button
          onClick={() => setActiveSection('settings')}
          className={`w-full text-left px-3 py-2 rounded text-sm font-medium transition-colors ${
            activeSection === 'settings'
              ? 'bg-shell-border text-shell-text'
              : 'text-shell-muted hover:text-shell-text hover:bg-shell-panel'
          }`}
        >
          Settings
        </button>
      </nav>
      <div className="p-3 text-xs text-shell-muted border-t border-shell-border">
        {activeSection === 'workflow' ? 'Workflow shell' : 'Edit configuration'}
      </div>
    </div>
  )

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-shell-bg">
      {/* Collapsible side panel */}
      <aside
        className={`flex-shrink-0 border-r border-shell-border bg-shell-panel transition-all duration-200 ${
          sidebarOpen ? 'w-56' : 'w-0 overflow-hidden'
        }`}
      >
        <SidebarContent />
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <header className="flex items-center gap-3 px-4 py-2 border-b border-shell-border bg-shell-panel">
          <button
            onClick={() => setSidebarOpen((open) => !open)}
            className="btn-ghost"
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarOpen ? '◀ Hide' : '▶ Show'}
          </button>
          <h2 className="text-sm font-medium text-shell-text capitalize">
            {activeSection}
          </h2>
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-hidden p-3">
          {activeSection === 'workflow' ? (
            <div className="flex h-full gap-3 overflow-x-auto">
              {WORKFLOW_PANELS.map((label) => (
                <section
                  key={label}
                  className="panel p-3 min-w-[240px] flex-1 flex flex-col"
                >
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted mb-2">
                    {label}
                  </h3>
                  <div className="flex-1 flex items-center justify-center rounded border border-dashed border-shell-border bg-shell-bg/50">
                    <span className="text-sm text-shell-muted">Placeholder</span>
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <SettingsForm />
          )}
        </div>
      </main>
    </div>
  )
}
