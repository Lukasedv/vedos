import React from 'react'
import { FilmType, AIModel, MaskRegion } from '../types'
import { ProcessingSettings, InversionParams } from '../hooks/useProcessing'

interface SettingsPanelProps {
  settings: ProcessingSettings
  onUpdateSettings: (partial: Partial<ProcessingSettings>) => void
  onUpdateInversion: (partial: Partial<InversionParams>) => void
}

const SettingsPanel: React.FC<SettingsPanelProps> = ({
  settings,
  onUpdateSettings,
  onUpdateInversion,
}) => {
  const { filmType, maskRegion, maskMode, inversion, aiEnabled, aiModel, aiRefine } = settings

  return (
    <aside className="settings-panel">
      <h2 className="settings-panel__title">Settings</h2>

      {/* Film Type */}
      <section className="settings-section">
        <h3 className="settings-section__heading">Film Type</h3>
        <label className="settings-radio">
          <input
            type="radio"
            name="filmType"
            value="color_negative"
            checked={filmType === 'color_negative'}
            onChange={() => onUpdateSettings({ filmType: 'color_negative' })}
          />
          <span className="settings-radio__label">Color Negative (C-41)</span>
          <span className="settings-radio__desc">Standard color negative film with orange mask</span>
        </label>
        <label className="settings-radio">
          <input
            type="radio"
            name="filmType"
            value="bw_negative"
            checked={filmType === 'bw_negative'}
            onChange={() => onUpdateSettings({ filmType: 'bw_negative' })}
          />
          <span className="settings-radio__label">B&amp;W Negative</span>
          <span className="settings-radio__desc">Black and white negative film</span>
        </label>
      </section>

      {/* Orange Mask Sampling — only for color negatives */}
      {filmType === 'color_negative' && (
        <section className="settings-section">
          <h3 className="settings-section__heading">Orange Mask Sampling</h3>
          <p className="settings-hint">
            Click and drag on an image to select the unexposed film border.
          </p>
          <div className="settings-mask-info">
            {maskRegion ? (
              <span className="settings-mask-coords">
                x:{maskRegion.x} y:{maskRegion.y} w:{maskRegion.w} h:{maskRegion.h}
              </span>
            ) : (
              <span className="settings-mask-auto">Auto-detect</span>
            )}
          </div>
          <div className="settings-btn-row">
            <button
              className="settings-btn settings-btn--secondary"
              onClick={() => onUpdateSettings({ maskRegion: null, maskMode: 'auto' })}
            >
              Auto Detect
            </button>
            <button
              className="settings-btn settings-btn--secondary"
              onClick={() => onUpdateSettings({ maskRegion: null, maskMode: 'auto' })}
            >
              Reset
            </button>
          </div>
        </section>
      )}

      {/* Inversion Parameters */}
      <section className="settings-section">
        <h3 className="settings-section__heading">Inversion Parameters</h3>

        <label className="settings-slider">
          <span className="settings-slider__label">
            Black Point: {inversion.blackPoint.toFixed(2)}%
          </span>
          <input
            type="range"
            min={0.01}
            max={2.0}
            step={0.01}
            value={inversion.blackPoint}
            onChange={(e) => onUpdateInversion({ blackPoint: parseFloat(e.target.value) })}
          />
        </label>

        <label className="settings-slider">
          <span className="settings-slider__label">
            White Point: {inversion.whitePoint.toFixed(2)}%
          </span>
          <input
            type="range"
            min={98.0}
            max={99.99}
            step={0.01}
            value={inversion.whitePoint}
            onChange={(e) => onUpdateInversion({ whitePoint: parseFloat(e.target.value) })}
          />
        </label>

        <label className="settings-slider">
          <span className="settings-slider__label">
            Contrast: {inversion.contrast.toFixed(2)}
          </span>
          <input
            type="range"
            min={0.5}
            max={2.0}
            step={0.01}
            value={inversion.contrast}
            onChange={(e) => onUpdateInversion({ contrast: parseFloat(e.target.value) })}
          />
        </label>
      </section>

      {/* AI Color Correction */}
      <section className="settings-section">
        <h3 className="settings-section__heading">AI Color Correction</h3>

        <label className="settings-toggle">
          <input
            type="checkbox"
            checked={aiEnabled}
            onChange={(e) => onUpdateSettings({ aiEnabled: e.target.checked })}
          />
          <span className="settings-toggle__label">
            {aiEnabled ? 'Enabled' : 'Disabled'}
          </span>
        </label>

        {aiEnabled && (
          <>
            <select
              className="settings-select"
              value={aiModel}
              onChange={(e) => onUpdateSettings({ aiModel: e.target.value as AIModel })}
            >
              <option value="claude-sonnet-4.5">Claude Sonnet 4.5 (Best quality)</option>
              <option value="claude-haiku-4.5">Claude Haiku 4.5 (Faster)</option>
            </select>

            <label className="settings-checkbox">
              <input
                type="checkbox"
                checked={aiRefine}
                onChange={(e) => onUpdateSettings({ aiRefine: e.target.checked })}
              />
              <span>Run a second AI pass for fine-tuning</span>
            </label>

            <p className="settings-note">
              Requires GitHub Copilot CLI to be installed and authenticated.
            </p>
          </>
        )}
      </section>
    </aside>
  )
}

export default SettingsPanel
