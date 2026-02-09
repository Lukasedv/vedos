import React from 'react'

interface StatusBarProps {
  fileCount: number
  selectedCount: number
  processingStatus?: string | null
}

const StatusBar: React.FC<StatusBarProps> = ({
  fileCount,
  selectedCount,
  processingStatus,
}) => {
  return (
    <div className="status-bar">
      <span className="status-bar__item">
        {fileCount} file{fileCount !== 1 ? 's' : ''} imported
      </span>
      <span className="status-bar__item">
        {selectedCount} selected
      </span>
      {processingStatus && (
        <span className="status-bar__item status-bar__item--processing">
          {processingStatus}
        </span>
      )}
    </div>
  )
}

export default StatusBar
