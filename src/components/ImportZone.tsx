import React, { useState, useCallback, useRef } from 'react'
import { RAW_EXTENSIONS } from '../types'

interface ImportZoneProps {
  hasFiles: boolean
  onFilesAdded: (paths: string[]) => void
  onBrowse: () => void
}

const ImportZone: React.FC<ImportZoneProps> = ({ hasFiles, onFilesAdded, onBrowse }) => {
  const [dragOver, setDragOver] = useState(false)
  const dragCounter = useRef(0)

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current++
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter.current--
    if (dragCounter.current === 0) setDragOver(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setDragOver(false)
      dragCounter.current = 0

      const droppedFiles = Array.from(e.dataTransfer.files)
      const paths = droppedFiles
        .filter((f) => {
          const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase()
          return RAW_EXTENSIONS.includes(ext)
        })
        .map((f) => (f as File & { path?: string }).path || f.name)

      if (paths.length > 0) {
        onFilesAdded(paths)
      } else if (droppedFiles.length > 0) {
        onFilesAdded(droppedFiles.map((f) => f.name)) // will trigger rejection notification
      }
    },
    [onFilesAdded]
  )

  if (hasFiles) {
    return (
      <div className="import-zone-compact">
        <button
          className="add-more-btn"
          onClick={onBrowse}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          + Add more files
        </button>
      </div>
    )
  }

  return (
    <div
      className={`import-zone ${dragOver ? 'import-zone--drag-over' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="import-zone__content">
        <div className="import-zone__icon">📁</div>
        <h2 className="import-zone__title">Import RAW Files</h2>
        <p className="import-zone__subtitle">
          Drag &amp; drop your RAW files here
        </p>
        <p className="import-zone__formats">
          Supported: ARW, CR2, NEF, RAF, DNG, ORF, RW2, PEF, SRW
        </p>
        <button className="import-zone__browse-btn" onClick={onBrowse}>
          Click to browse
        </button>
      </div>
    </div>
  )
}

export default ImportZone
