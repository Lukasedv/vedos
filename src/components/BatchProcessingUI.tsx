import React from 'react'
import { FileResult } from '../hooks/useProcessing'

interface BatchProcessingUIProps {
  progress: number
  currentFileIndex: number
  totalFiles: number
  fileResults: FileResult[]
  currentStep: string
  estimatedTimeRemaining: number | null
  isComplete: boolean
  onCancel: () => void
  onReset: () => void
  onOpenOutputFolder: () => void
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

const statusIcon = (status: FileResult['status']) => {
  switch (status) {
    case 'done':
      return '✅'
    case 'processing':
      return '🔄'
    case 'queued':
      return '⏳'
    case 'error':
      return '❌'
  }
}

const BatchProcessingUI: React.FC<BatchProcessingUIProps> = ({
  progress,
  currentFileIndex,
  totalFiles,
  fileResults,
  currentStep,
  estimatedTimeRemaining,
  isComplete,
  onCancel,
  onReset,
  onOpenOutputFolder,
}) => {
  const completedCount = fileResults.filter((r) => r.status === 'done').length
  const errorCount = fileResults.filter((r) => r.status === 'error').length

  return (
    <div className="batch-overlay">
      <div className="batch-modal">
        <h2 className="batch-modal__title">
          {isComplete ? 'Processing Complete' : 'Processing Files'}
        </h2>

        {/* Progress bar */}
        <div className="batch-progress">
          <div className="batch-progress__bar">
            <div
              className="batch-progress__fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="batch-progress__info">
            {isComplete ? (
              <span>Done — {completedCount} of {totalFiles} files converted</span>
            ) : (
              <span>Processing {currentFileIndex + 1} of {totalFiles} files…</span>
            )}
            <span>{progress}%</span>
          </div>
        </div>

        {/* Current step */}
        {!isComplete && currentStep && (
          <div className="batch-step">
            Current step: <strong>{currentStep}</strong>
          </div>
        )}

        {/* Estimated time */}
        {!isComplete && estimatedTimeRemaining !== null && (
          <div className="batch-eta">
            Estimated time remaining: {formatTime(estimatedTimeRemaining)}
          </div>
        )}

        {/* File list */}
        <ul className="batch-file-list">
          {fileResults.map((r) => (
            <li
              key={r.id}
              className={`batch-file-item batch-file-item--${r.status}`}
            >
              <span className="batch-file-item__icon">{statusIcon(r.status)}</span>
              <span className="batch-file-item__name">{r.filename}</span>
              {r.status === 'processing' && r.currentStep && (
                <span className="batch-file-item__step">{r.currentStep}</span>
              )}
              {r.status === 'error' && r.error && (
                <span className="batch-file-item__error">{r.error}</span>
              )}
            </li>
          ))}
        </ul>

        {/* Summary on completion */}
        {isComplete && (
          <div className="batch-summary">
            <span className="batch-summary__stat">✅ {completedCount} converted</span>
            {errorCount > 0 && (
              <span className="batch-summary__stat batch-summary__stat--error">
                ❌ {errorCount} failed
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="batch-actions">
          {isComplete ? (
            <>
              <button className="batch-btn batch-btn--primary" onClick={onOpenOutputFolder}>
                Open Output Folder
              </button>
              <button className="batch-btn batch-btn--secondary" onClick={onReset}>
                Done
              </button>
            </>
          ) : (
            <button className="batch-btn batch-btn--cancel" onClick={onCancel}>
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default BatchProcessingUI
