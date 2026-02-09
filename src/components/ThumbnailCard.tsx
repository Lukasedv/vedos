import React from 'react'
import { ImportedFile } from '../types'
import { formatFileSize } from '../hooks/useFiles'

interface ThumbnailCardProps {
  file: ImportedFile
  selected: boolean
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onDoubleClick?: (id: string) => void
}

const ThumbnailCard: React.FC<ThumbnailCardProps> = ({
  file,
  selected,
  onSelect,
  onToggle,
  onDoubleClick,
}) => {
  const handleClick = (e: React.MouseEvent) => {
    if (e.metaKey || e.ctrlKey) {
      onToggle(file.id)
    } else {
      onSelect(file.id)
    }
  }

  const handleDoubleClick = () => {
    onDoubleClick?.(file.id)
  }

  const handleCheckbox = (e: React.MouseEvent) => {
    e.stopPropagation()
    onToggle(file.id)
  }

  return (
    <div
      className={`thumbnail-card ${selected ? 'thumbnail-card--selected' : ''}`}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
    >
      <div className="thumbnail-card__checkbox" onClick={handleCheckbox}>
        <input type="checkbox" checked={selected} readOnly tabIndex={-1} />
      </div>
      <div className="thumbnail-card__preview">
        <span className="thumbnail-card__placeholder-text">RAW</span>
      </div>
      <div className="thumbnail-card__info">
        <span className="thumbnail-card__filename" title={file.filename}>
          {file.filename}
        </span>
        <div className="thumbnail-card__meta">
          <span className="thumbnail-card__badge">{file.format}</span>
          <span className="thumbnail-card__size">
            {formatFileSize(file.fileSize)}
          </span>
        </div>
      </div>
    </div>
  )
}

export default ThumbnailCard
