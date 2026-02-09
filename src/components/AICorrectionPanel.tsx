import React, { useState, useCallback } from 'react'
import { CorrectionResult, AICorrectionParams } from '../types'

interface AICorrectionPanelProps {
  corrections: CorrectionResult[]
  currentIndex: number
  onNavigate: (index: number) => void
  onAccept: (fileIndex: number) => void
  onReject: (fileIndex: number) => void
  onReanalyze: (fileIndex: number) => void
  onApplyManual: (fileIndex: number, params: ManualParams) => void
  onAcceptAll: () => void
  onClose: () => void
}

interface ManualParams {
  white_balance_shift: number
  tint_shift: number
  exposure_compensation: number
  saturation_adjustment: number
}

const formatValue = (value: number, suffix: string, showSign = true): string => {
  const sign = showSign && value > 0 ? '+' : ''
  return `${sign}${value}${suffix}`
}

const CurveBar: React.FC<{ label: string; value: number }> = ({ label, value }) => {
  const pct = Math.abs(value) * 2 // scale ±50 to 0-100%
  const isPositive = value >= 0
  return (
    <div className="ai-correction__curve-bar">
      <span className="ai-correction__curve-label">{label}</span>
      <div className="ai-correction__curve-track">
        <div className="ai-correction__curve-center" />
        <div
          className={`ai-correction__curve-fill ${isPositive ? 'ai-correction__curve-fill--pos' : 'ai-correction__curve-fill--neg'}`}
          style={{
            width: `${pct}%`,
            [isPositive ? 'left' : 'right']: '50%',
          }}
        />
      </div>
      <span className="ai-correction__curve-value">{formatValue(value, '')}</span>
    </div>
  )
}

const AICorrectionPanel: React.FC<AICorrectionPanelProps> = ({
  corrections,
  currentIndex,
  onNavigate,
  onAccept,
  onReject,
  onReanalyze,
  onApplyManual,
  onAcceptAll,
  onClose,
}) => {
  const current = corrections[currentIndex]
  const [splitPosition, setSplitPosition] = useState(50)
  const [isDragging, setIsDragging] = useState(false)

  const [manualWB, setManualWB] = useState(current?.corrections.white_balance_shift ?? 0)
  const [manualTint, setManualTint] = useState(current?.corrections.tint_shift ?? 0)
  const [manualExposure, setManualExposure] = useState(current?.corrections.exposure_compensation ?? 0)
  const [manualSaturation, setManualSaturation] = useState(current?.corrections.saturation_adjustment ?? 0)

  // Reset sliders when navigating to a different file
  const handleNavigate = useCallback(
    (index: number) => {
      onNavigate(index)
      const c = corrections[index]
      if (c) {
        setManualWB(c.corrections.white_balance_shift)
        setManualTint(c.corrections.tint_shift)
        setManualExposure(c.corrections.exposure_compensation)
        setManualSaturation(c.corrections.saturation_adjustment ?? 0)
      }
    },
    [corrections, onNavigate]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isDragging) return
      const rect = e.currentTarget.getBoundingClientRect()
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      setSplitPosition(Math.max(5, Math.min(95, pct)))
    },
    [isDragging]
  )

  if (!current) {
    return (
      <div className="ai-correction">
        <p>No AI corrections to review.</p>
        <button className="ai-correction__btn" onClick={onClose}>Close</button>
      </div>
    )
  }

  const { corrections: params, analysisNotes } = current
  const curves = params.curves

  return (
    <div className="ai-correction">
      {/* Header */}
      <div className="ai-correction__header">
        <h2 className="ai-correction__title">AI Correction Review</h2>
        <div className="ai-correction__nav">
          <button
            className="ai-correction__btn ai-correction__btn--small"
            disabled={currentIndex <= 0}
            onClick={() => handleNavigate(currentIndex - 1)}
          >
            ◀ Prev
          </button>
          <span className="ai-correction__counter">
            {currentIndex + 1} / {corrections.length} — {current.filename}
          </span>
          <button
            className="ai-correction__btn ai-correction__btn--small"
            disabled={currentIndex >= corrections.length - 1}
            onClick={() => handleNavigate(currentIndex + 1)}
          >
            Next ▶
          </button>
        </div>
      </div>

      <div className="ai-correction__body">
        {/* Before/After split view */}
        <div
          className="ai-correction__preview"
          onMouseMove={handleMouseMove}
          onMouseUp={() => setIsDragging(false)}
          onMouseLeave={() => setIsDragging(false)}
        >
          <div
            className="ai-correction__preview-before"
            style={{ width: `${splitPosition}%` }}
          >
            <img src={current.beforePreviewUrl} alt="Before" />
            <span className="ai-correction__preview-label">Before</span>
          </div>
          <div
            className="ai-correction__preview-after"
            style={{ width: `${100 - splitPosition}%` }}
          >
            <img src={current.afterPreviewUrl} alt="After" />
            <span className="ai-correction__preview-label">After</span>
          </div>
          <div
            className="ai-correction__preview-divider"
            style={{ left: `${splitPosition}%` }}
            onMouseDown={(e) => {
              e.preventDefault()
              setIsDragging(true)
            }}
          />
        </div>

        {/* Sidebar with details and sliders */}
        <div className="ai-correction__sidebar">
          {/* Correction details */}
          <section className="ai-correction__section">
            <h3 className="ai-correction__section-title">Detected Corrections</h3>
            <div className="ai-correction__detail">
              <span>White Balance</span>
              <strong>{formatValue(params.white_balance_shift, 'K')}</strong>
            </div>
            <div className="ai-correction__detail">
              <span>Tint</span>
              <strong>{formatValue(params.tint_shift, '')}</strong>
            </div>
            <div className="ai-correction__detail">
              <span>Exposure</span>
              <strong>{formatValue(params.exposure_compensation, ' EV')}</strong>
            </div>
            <div className="ai-correction__detail">
              <span>Saturation</span>
              <strong>{formatValue(params.saturation_adjustment ?? 0, '')}</strong>
            </div>
          </section>

          {/* Per-channel curves */}
          <section className="ai-correction__section">
            <h3 className="ai-correction__section-title">Channel Curves</h3>
            <div className="ai-correction__curves-group">
              <span className="ai-correction__channel-label" style={{ color: '#e55' }}>Red</span>
              <CurveBar label="S" value={curves.r.shadows} />
              <CurveBar label="M" value={curves.r.midtones} />
              <CurveBar label="H" value={curves.r.highlights} />
            </div>
            <div className="ai-correction__curves-group">
              <span className="ai-correction__channel-label" style={{ color: '#5b5' }}>Green</span>
              <CurveBar label="S" value={curves.g.shadows} />
              <CurveBar label="M" value={curves.g.midtones} />
              <CurveBar label="H" value={curves.g.highlights} />
            </div>
            <div className="ai-correction__curves-group">
              <span className="ai-correction__channel-label" style={{ color: '#55e' }}>Blue</span>
              <CurveBar label="S" value={curves.b.shadows} />
              <CurveBar label="M" value={curves.b.midtones} />
              <CurveBar label="H" value={curves.b.highlights} />
            </div>
          </section>

          {/* Analysis notes */}
          {analysisNotes && (
            <section className="ai-correction__section ai-correction__notes">
              <h3 className="ai-correction__section-title">AI Analysis Notes</h3>
              <p className="ai-correction__notes-text">{analysisNotes}</p>
            </section>
          )}

          {/* Manual override sliders */}
          <section className="ai-correction__section">
            <h3 className="ai-correction__section-title">Manual Override</h3>

            <label className="ai-correction__slider">
              <span>WB: {formatValue(manualWB, 'K')}</span>
              <input
                type="range"
                min={-3000}
                max={3000}
                step={50}
                value={manualWB}
                onChange={(e) => setManualWB(Number(e.target.value))}
              />
            </label>

            <label className="ai-correction__slider">
              <span>Tint: {formatValue(manualTint, '')}</span>
              <input
                type="range"
                min={-50}
                max={50}
                step={1}
                value={manualTint}
                onChange={(e) => setManualTint(Number(e.target.value))}
              />
            </label>

            <label className="ai-correction__slider">
              <span>Exposure: {formatValue(manualExposure, ' EV')}</span>
              <input
                type="range"
                min={-2.0}
                max={2.0}
                step={0.05}
                value={manualExposure}
                onChange={(e) => setManualExposure(Number(e.target.value))}
              />
            </label>

            <label className="ai-correction__slider">
              <span>Saturation: {formatValue(manualSaturation, '')}</span>
              <input
                type="range"
                min={-50}
                max={50}
                step={1}
                value={manualSaturation}
                onChange={(e) => setManualSaturation(Number(e.target.value))}
              />
            </label>
          </section>

          {/* Action buttons */}
          <section className="ai-correction__actions">
            <button
              className="ai-correction__btn ai-correction__btn--primary"
              onClick={() => onAccept(current.fileIndex)}
            >
              Accept
            </button>
            <button
              className="ai-correction__btn ai-correction__btn--danger"
              onClick={() => onReject(current.fileIndex)}
            >
              Reject
            </button>
            <button
              className="ai-correction__btn ai-correction__btn--secondary"
              onClick={() => onReanalyze(current.fileIndex)}
            >
              Re-analyze
            </button>
            <button
              className="ai-correction__btn ai-correction__btn--secondary"
              onClick={() =>
                onApplyManual(current.fileIndex, {
                  white_balance_shift: manualWB,
                  tint_shift: manualTint,
                  exposure_compensation: manualExposure,
                  saturation_adjustment: manualSaturation,
                })
              }
            >
              Apply Manual
            </button>
            <hr className="ai-correction__divider" />
            <button
              className="ai-correction__btn ai-correction__btn--primary ai-correction__btn--wide"
              onClick={onAcceptAll}
            >
              Accept All
            </button>
          </section>
        </div>
      </div>
    </div>
  )
}

export default AICorrectionPanel
