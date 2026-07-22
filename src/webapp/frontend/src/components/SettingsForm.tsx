import { useEffect, useState } from 'react'
import { fetchSettings, saveSettings } from '../api'
import type {
  AppSettings,
  MdGenSummarySettings,
  MdMrgScoreSettings,
  MdMrgSummarySettings,
  ValidationError,
} from '../types'

interface FieldErrors {
  [key: string]: string
}

const DEFAULT_MD_GEN_SUMMARY: MdGenSummarySettings = {
  system_prompt: '',
  assistant_prompt: '',
  temperature: 0.7,
}

const DEFAULT_MD_MRG_SCORE: MdMrgScoreSettings = {
  system_prompt: '',
  assistant_prompt: '',
  temperature: 0.7,
}

const DEFAULT_MD_MRG_SUMMARY: MdMrgSummarySettings = {
  system_prompt: '',
  assistant_prompt: '',
  temperature: 0.7,
}

function normalizeSettings(settings: AppSettings): AppSettings {
  return {
    ...settings,
    md_gen: {
      ...settings.md_gen,
      summary: {
        ...DEFAULT_MD_GEN_SUMMARY,
        ...settings.md_gen?.summary,
      },
    },
    md_mrg: {
      ...settings.md_mrg,
      score: {
        ...DEFAULT_MD_MRG_SCORE,
        ...settings.md_mrg?.score,
      },
      summary: {
        ...DEFAULT_MD_MRG_SUMMARY,
        ...settings.md_mrg?.summary,
      },
    },
  }
}

function buildFieldErrors(errors: ValidationError[]): FieldErrors {
  const result: FieldErrors = {}
  for (const err of errors) {
    const path = err.loc[0] === 'body' ? err.loc.slice(1) : err.loc
    const key = path.join('.')
    result[key] = err.msg
  }
  return result
}

function getFieldError(errors: FieldErrors, ...path: (string | number)[]): string {
  return errors[path.join('.')] || ''
}

function updateModel<K extends keyof AppSettings>(
  settings: AppSettings,
  key: K,
  value: AppSettings[K],
): AppSettings {
  return { ...settings, [key]: value }
}

function updateNested<T>(parent: T, key: keyof T, value: T[keyof T]): T {
  return { ...parent, [key]: value }
}

export default function SettingsForm() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    fetchSettings()
      .then((data) => {
        setSettings(normalizeSettings(data))
        setLoading(false)
      })
      .catch((err: Error) => {
        setLoadError(err.message)
        setLoading(false)
      })
  }, [])

  const handleChange = (setter: () => AppSettings) => {
    setSettings(setter())
    setSaveSuccess(false)
    setFieldErrors({})
    setSaveError('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!settings) return

    setSaving(true)
    setSaveSuccess(false)
    setSaveError('')
    setFieldErrors({})

    const result = await saveSettings(settings)
    setSaving(false)

    if (result.ok) {
      setSaveSuccess(true)
      if (result.settings) {
        setSettings(normalizeSettings(result.settings))
      }
      window.setTimeout(() => setSaveSuccess(false), 3000)
      return
    }

    if (result.validationErrors) {
      setFieldErrors(buildFieldErrors(result.validationErrors))
      return
    }

    setSaveError(result.error || 'Save failed')
  }

  if (loading) {
    return (
      <div className="panel p-6">
        <p className="text-shell-muted">Loading settings...</p>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="panel p-6">
        <p className="text-red-400">{loadError}</p>
      </div>
    )
  }

  if (!settings) {
    return null
  }

  return (
    <form onSubmit={handleSubmit} className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto pr-2 space-y-3">
        {saveSuccess && (
          <div className="rounded bg-emerald-900/30 border border-emerald-800 px-3 py-1.5 text-sm text-emerald-300">
            Settings saved successfully.
          </div>
        )}
        {saveError && (
          <div className="rounded bg-red-900/30 border border-red-800 px-3 py-1.5 text-sm text-red-300">
            {saveError}
          </div>
        )}

        <section className="panel p-3 space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
            Folders
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-shell-muted mb-0.5">
                Source folder
              </label>
              <input
                type="text"
                className="input-field py-1.5"
                value={settings.source_folder}
                onChange={(e) =>
                  handleChange(() =>
                    updateModel(settings, 'source_folder', e.target.value),
                  )
                }
              />
              {fieldErrors['source_folder'] && (
                <p className="mt-0.5 text-xs text-red-400">
                  {fieldErrors['source_folder']}
                </p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-shell-muted mb-0.5">
                Output folder
              </label>
              <input
                type="text"
                className="input-field py-1.5"
                value={settings.output_folder}
                onChange={(e) =>
                  handleChange(() =>
                    updateModel(settings, 'output_folder', e.target.value),
                  )
                }
              />
              {fieldErrors['output_folder'] && (
                <p className="mt-0.5 text-xs text-red-400">
                  {fieldErrors['output_folder']}
                </p>
              )}
            </div>
          </div>
        </section>

        <section className="panel p-3 space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
            Runtime options
          </h3>
          <div className="flex flex-wrap gap-4">
            <label className="inline-flex items-center gap-2 text-sm text-shell-text cursor-pointer">
              <input
                type="checkbox"
                className="rounded border-shell-border bg-shell-bg text-accent focus:ring-accent"
                checked={settings.verbose}
                onChange={(e) =>
                  handleChange(() =>
                    updateModel(settings, 'verbose', e.target.checked),
                  )
                }
              />
              Verbose
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-shell-text cursor-pointer">
              <input
                type="checkbox"
                className="rounded border-shell-border bg-shell-bg text-accent focus:ring-accent"
                checked={settings.overwrite}
                onChange={(e) =>
                  handleChange(() =>
                    updateModel(settings, 'overwrite', e.target.checked),
                  )
                }
              />
              Overwrite
            </label>
          </div>
        </section>

        <section className="panel p-3 space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
            Model endpoints
          </h3>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-shell-text">OCR model</h4>
              <div>
                <label className="block text-xs font-medium text-shell-muted mb-0.5">
                  Endpoint
                </label>
                <input
                  type="text"
                  className="input-field py-1.5"
                  value={settings.ocr_model.endpoint}
                  onChange={(e) =>
                    handleChange(() => ({
                      ...settings,
                      ocr_model: updateNested(settings.ocr_model, 'endpoint', e.target.value),
                    }))
                  }
                />
                {getFieldError(fieldErrors, 'ocr_model', 'endpoint') && (
                  <p className="mt-0.5 text-xs text-red-400">
                    {getFieldError(fieldErrors, 'ocr_model', 'endpoint')}
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Model
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.ocr_model.model}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        ocr_model: updateNested(settings.ocr_model, 'model', e.target.value),
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Timeout (s)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    className="input-field py-1.5"
                    value={settings.ocr_model.timeout_seconds}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        ocr_model: updateNested(
                          settings.ocr_model,
                          'timeout_seconds',
                          Number(e.target.value),
                        ),
                      }))
                    }
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-shell-muted mb-0.5">
                  Max retries
                </label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  className="input-field py-1.5"
                  value={settings.ocr_model.max_retries}
                  onChange={(e) =>
                    handleChange(() => ({
                      ...settings,
                      ocr_model: updateNested(
                        settings.ocr_model,
                        'max_retries',
                        Number(e.target.value),
                      ),
                    }))
                  }
                />
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-medium text-shell-text">Language model</h4>
              <div>
                <label className="block text-xs font-medium text-shell-muted mb-0.5">
                  Endpoint
                </label>
                <input
                  type="text"
                  className="input-field py-1.5"
                  value={settings.language_model.endpoint}
                  onChange={(e) =>
                    handleChange(() => ({
                      ...settings,
                      language_model: updateNested(
                        settings.language_model,
                        'endpoint',
                        e.target.value,
                      ),
                    }))
                  }
                />
                {getFieldError(fieldErrors, 'language_model', 'endpoint') && (
                  <p className="mt-0.5 text-xs text-red-400">
                    {getFieldError(fieldErrors, 'language_model', 'endpoint')}
                  </p>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Model
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.language_model.model}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        language_model: updateNested(
                          settings.language_model,
                          'model',
                          e.target.value,
                        ),
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Timeout (s)
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    className="input-field py-1.5"
                    value={settings.language_model.timeout_seconds}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        language_model: updateNested(
                          settings.language_model,
                          'timeout_seconds',
                          Number(e.target.value),
                        ),
                      }))
                    }
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-shell-muted mb-0.5">
                  Max retries
                </label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  className="input-field py-1.5"
                  value={settings.language_model.max_retries}
                  onChange={(e) =>
                    handleChange(() => ({
                      ...settings,
                      language_model: updateNested(
                        settings.language_model,
                        'max_retries',
                        Number(e.target.value),
                      ),
                    }))
                  }
                />
              </div>
            </div>
          </div>
        </section>

        <section className="panel p-3 space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-shell-muted">
            Prompts
          </h3>
          <div className="space-y-3">
            <div>
              <h4 className="text-sm font-medium text-shell-text mb-1">md-gen summary</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    System prompt path
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.md_gen.summary.system_prompt}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        md_gen: updateNested(settings.md_gen, 'summary', {
                          ...settings.md_gen.summary,
                          system_prompt: e.target.value,
                        }),
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Assistant prompt path
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.md_gen.summary.assistant_prompt}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        md_gen: updateNested(settings.md_gen, 'summary', {
                          ...settings.md_gen.summary,
                          assistant_prompt: e.target.value,
                        }),
                      }))
                    }
                  />
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-shell-text mb-1">md-mrg score</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    System prompt path
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.md_mrg.score.system_prompt}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        md_mrg: updateNested(settings.md_mrg, 'score', {
                          ...settings.md_mrg.score,
                          system_prompt: e.target.value,
                        }),
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Assistant prompt path
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.md_mrg.score.assistant_prompt}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        md_mrg: updateNested(settings.md_mrg, 'score', {
                          ...settings.md_mrg.score,
                          assistant_prompt: e.target.value,
                        }),
                      }))
                    }
                  />
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-shell-text mb-1">md-mrg summary</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    System prompt path
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.md_mrg.summary.system_prompt}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        md_mrg: updateNested(settings.md_mrg, 'summary', {
                          ...settings.md_mrg.summary,
                          system_prompt: e.target.value,
                        }),
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-shell-muted mb-0.5">
                    Assistant prompt path
                  </label>
                  <input
                    type="text"
                    className="input-field py-1.5"
                    value={settings.md_mrg.summary.assistant_prompt}
                    onChange={(e) =>
                      handleChange(() => ({
                        ...settings,
                        md_mrg: updateNested(settings.md_mrg, 'summary', {
                          ...settings.md_mrg.summary,
                          assistant_prompt: e.target.value,
                        }),
                      }))
                    }
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="flex items-center gap-3 pt-2 border-t border-shell-border">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? 'Saving...' : 'Save settings'}
        </button>
        {saveSuccess && (
          <span className="text-sm text-emerald-400">Saved!</span>
        )}
      </div>
    </form>
  )
}
