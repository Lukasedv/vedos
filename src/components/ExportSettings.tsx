import React from 'react'
import { ExportConfig } from '../hooks/useProcessing'

interface ExportSettingsProps {
  config: ExportConfig
  onUpdate: (partial: Partial<ExportConfig>) => void
  selectedCount: number
  onStartProcessing: () => void
  onCancel: () => void
}

const NAMING_PATTERNS = [
  { value: '{original}_positive', label: '{original}_positive' },
  { value: '{original}_converted', label: '{original}_converted' },
  { value: '{original}_inv', label: '{original}_inv' },
  { value: 'custom', label: 'Custom pattern…' },
]

const ExportSettings: React.FC<ExportSettingsProps> = ({
  config,
  onUpdate,
  selectedCount,
  onStartProcessing,
  onCancel,
}) => {
  const handleBrowse = async () => {
    try {
      const api = (
        window as Window & { vedos?: { selectDirectory: () => Promise<string> } }
      ).vedos
      if (api?.selectDirectory) {
        const dir = await api.selectDirectory()
        if (dir) onUpdate({ outputDir: dir })
      }
    } catch {
      // Dev fallback — no-op
    }
  }

  const isCustom = !NAMING_PATTERNS.some(
    (p) => p.value === config.namingPattern && p.value !== 'custom'
  )
  const selectValue = isCustom ? 'custom' : config.namingPattern

  return (
    <div className="export-overlay">
      <div className="export-modal">
        <h2 className="export-modal__title">Export Settings</h2>

        {/* Output directory */}
        <label className="export-field">
          <span className="export-field__label">Output Directory</span>
          <div className="export-field__row">
            <input
              type="text"
              className="export-input"
              value={config.outputDir}
              onChange={(e) => onUpdate({ outputDir: e.target.value })}
              placeholder="Select output folder…"
            />
            <button className="export-btn export-btn--browse" onClick={handleBrowse}>
              Browse
            </button>
          </div>
        </label>

        {/* Output format */}
        <label className="export-field">
          <span className="export-field__label">Output Format</span>
          <select
            className="export-select"
            value={config.outputFormat}
            onChange={(e) => onUpdate({ outputFormat: e.target.value })}
          >
            <option value="dng">DNG (Adobe Digital Negative)</option>
          </select>
        </label>

        {/* Naming pattern */}
        <label className="export-field">
          <span className="export-field__label">File Naming</span>
          <select
            className="export-select"
            value={selectValue}
            onChange={(e) => {
              const v = e.target.value
              if (v !== 'custom') onUpdate({ namingPattern: v })
            }}
          >
            {NAMING_PATTERNS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>

        {selectValue === 'custom' && (
          <label className="export-field">
            <span className="export-field__label">Custom Pattern</span>
            <input
              type="text"
              className="export-input"
              value={config.namingPattern}
              onChange={(e) => onUpdate({ namingPattern: e.target.value })}
              placeholder="{original}_custom"
            />
          </label>
        )}

        {/* Overwrite */}
        <label className="export-checkbox">
          <input
            type="checkbox"
            checked={config.overwrite}
            onChange={(e) => onUpdate({ overwrite: e.target.checked })}
          />
          <span>Overwrite existing files</span>
        </label>

        {/* Actions */}
        <div className="export-actions">
          <button className="export-btn export-btn--secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="export-btn export-btn--primary" onClick={onStartProcessing}>
            Start Processing ({selectedCount} files)
          </button>
        </div>
      </div>
    </div>
  )
}

export default ExportSettings
