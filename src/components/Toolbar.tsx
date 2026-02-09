import React from 'react'
import { FilmType, AIModel } from '../types'

interface ToolbarProps {
  filmType: FilmType
  onFilmTypeChange: (type: FilmType) => void
  aiEnabled: boolean
  onAiToggle: (enabled: boolean) => void
  aiModel: AIModel
  onAiModelChange: (model: AIModel) => void
  selectedCount: number
  onProcessSelected: () => void
}

const Toolbar: React.FC<ToolbarProps> = ({
  filmType,
  onFilmTypeChange,
  aiEnabled,
  onAiToggle,
  aiModel,
  onAiModelChange,
  selectedCount,
  onProcessSelected,
}) => {
  return (
    <div className="toolbar">
      <div className="toolbar__left">
        <span className="toolbar__title">Vedos</span>
      </div>
      <div className="toolbar__right">
        <select
          className="toolbar__select"
          value={filmType}
          onChange={(e) => onFilmTypeChange(e.target.value as FilmType)}
        >
          <option value="color_negative">Color Negative (C-41)</option>
          <option value="bw_negative">B&amp;W Negative</option>
        </select>

        <label className="toolbar__toggle">
          <input
            type="checkbox"
            checked={aiEnabled}
            onChange={(e) => onAiToggle(e.target.checked)}
          />
          <span className="toolbar__toggle-label">AI Correction</span>
        </label>

        {aiEnabled && (
          <select
            className="toolbar__select"
            value={aiModel}
            onChange={(e) => onAiModelChange(e.target.value as AIModel)}
          >
            <option value="claude-sonnet-4.5">Claude Sonnet 4.5</option>
            <option value="claude-haiku-4.5">Claude Haiku 4.5</option>
          </select>
        )}

        <button
          className="toolbar__process-btn"
          disabled={selectedCount === 0}
          onClick={onProcessSelected}
        >
          Process Selected ({selectedCount})
        </button>
      </div>
    </div>
  )
}

export default Toolbar
