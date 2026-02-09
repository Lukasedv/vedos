import React from 'react'
import { ImportedFile } from '../types'
import ThumbnailCard from './ThumbnailCard'

interface ThumbnailGridProps {
  files: ImportedFile[]
  selectedIds: Set<string>
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onSelectAll: () => void
  onClearSelection: () => void
  onPreview?: (id: string) => void
}

const ThumbnailGrid: React.FC<ThumbnailGridProps> = ({
  files,
  selectedIds,
  onSelect,
  onToggle,
  onSelectAll,
  onClearSelection,
  onPreview,
}) => {
  return (
    <div className="thumbnail-grid-container">
      <div className="thumbnail-grid__controls">
        <button className="grid-control-btn" onClick={onSelectAll}>
          Select All
        </button>
        <button className="grid-control-btn" onClick={onClearSelection}>
          Deselect All
        </button>
      </div>
      <div className="thumbnail-grid">
        {files.map((file) => (
          <ThumbnailCard
            key={file.id}
            file={file}
            selected={selectedIds.has(file.id)}
            onSelect={onSelect}
            onToggle={onToggle}
            onDoubleClick={onPreview}
          />
        ))}
      </div>
    </div>
  )
}

export default ThumbnailGrid
