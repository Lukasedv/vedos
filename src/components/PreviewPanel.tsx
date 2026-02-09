import React, { useState, useCallback, useRef, useEffect } from 'react'
import { ImportedFile, FilmType } from '../types'

type ViewMode = 'split' | 'single' | 'overlay'

interface PreviewPanelProps {
  file: ImportedFile
  filmType: FilmType
  files: ImportedFile[]
  currentIndex: number
  onNavigate: (index: number) => void
  onBack: () => void
  onSelectMaskRegion?: () => void
}

const MIN_ZOOM = 0.25
const MAX_ZOOM = 4.0
const ZOOM_STEP = 0.1

const PreviewPanel: React.FC<PreviewPanelProps> = ({
  file,
  filmType,
  files,
  currentIndex,
  onNavigate,
  onBack,
  onSelectMaskRegion,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('split')
  const [zoom, setZoom] = useState(1)
  const [isFit, setIsFit] = useState(true)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [splitPosition, setSplitPosition] = useState(50)
  const [isDraggingSplit, setIsDraggingSplit] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Placeholder dimensions
  const imgWidth = 6000
  const imgHeight = 4000

  const fitToWindow = useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setIsFit(true)
  }, [])

  const setZoomLevel = useCallback((z: number) => {
    const clamped = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z))
    setZoom(clamped)
    setIsFit(false)
  }, [])

  const zoomIn = useCallback(() => setZoomLevel(zoom + ZOOM_STEP), [zoom, setZoomLevel])
  const zoomOut = useCallback(() => setZoomLevel(zoom - ZOOM_STEP), [zoom, setZoomLevel])

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault()
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
      setZoomLevel(zoom + delta)
    },
    [zoom, setZoomLevel]
  )

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onBack()
        return
      }
      if (e.key === 'ArrowLeft' && currentIndex > 0) {
        onNavigate(currentIndex - 1)
        return
      }
      if (e.key === 'ArrowRight' && currentIndex < files.length - 1) {
        onNavigate(currentIndex + 1)
        return
      }
      if (e.key === '=' || e.key === '+') {
        zoomIn()
        return
      }
      if (e.key === '-') {
        zoomOut()
        return
      }
      if (e.key === '0') {
        fitToWindow()
        return
      }
      if (e.key === '1') {
        setZoomLevel(1)
        return
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [currentIndex, files.length, onNavigate, onBack, zoomIn, zoomOut, fitToWindow, setZoomLevel])

  // Pan handlers
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (isFit && zoom <= 1) return
      setIsPanning(true)
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
    },
    [pan, isFit, zoom]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning) {
        setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y })
      }
      if (isDraggingSplit && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        const pct = ((e.clientX - rect.left) / rect.width) * 100
        setSplitPosition(Math.max(5, Math.min(95, pct)))
      }
    },
    [isPanning, panStart, isDraggingSplit]
  )

  const handleMouseUp = useCallback(() => {
    setIsPanning(false)
    setIsDraggingSplit(false)
  }, [])

  // Reset pan/zoom on file change
  useEffect(() => {
    fitToWindow()
    setSplitPosition(50)
  }, [file.id, fitToWindow])

  const filmBadge = filmType === 'color_negative' ? 'C-41 Color' : 'B&W'

  const imageStyle: React.CSSProperties = isFit
    ? { width: '100%', height: '100%', objectFit: 'contain' as const }
    : {
        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
        transformOrigin: 'center center',
        transition: isPanning ? 'none' : 'transform 0.15s ease',
      }

  const renderPlaceholder = (type: 'negative' | 'positive') => {
    const bg =
      type === 'negative'
        ? 'linear-gradient(135deg, #3d2a1a 0%, #5a3a1e 50%, #3d2a1a 100%)'
        : 'linear-gradient(135deg, #2a2a2a 0%, #3d3d3d 50%, #2a2a2a 100%)'
    const label = type === 'negative' ? 'Negative' : 'Positive'

    return (
      <div className="preview-placeholder" style={{ background: bg }}>
        <div className="preview-placeholder__content">
          <span className="preview-placeholder__icon">
            {type === 'negative' ? '🎞️' : '🖼️'}
          </span>
          <span className="preview-placeholder__label">{label}</span>
          <span className="preview-placeholder__dims">
            {imgWidth} × {imgHeight}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div
      className="preview-panel"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Header */}
      <div className="preview-header">
        <button className="preview-header__back" onClick={onBack} title="Back to grid (Esc)">
          ← Back
        </button>
        <div className="preview-header__info">
          <span className="preview-header__filename">{file.filename}</span>
          <span className="preview-header__dims">
            {imgWidth} × {imgHeight}
          </span>
          <span className="preview-header__badge">{filmBadge}</span>
          <span className="preview-header__format">{file.format}</span>
        </div>
        <div className="preview-header__spacer" />
      </div>

      {/* Toolbar */}
      <div className="preview-toolbar">
        <div className="preview-toolbar__group">
          {(['split', 'single', 'overlay'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              className={`preview-toolbar__btn ${viewMode === mode ? 'preview-toolbar__btn--active' : ''}`}
              onClick={() => setViewMode(mode)}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>

        <div className="preview-toolbar__group">
          <button className="preview-toolbar__btn" onClick={zoomOut} title="Zoom out (-)">
            −
          </button>
          <input
            type="range"
            className="preview-toolbar__zoom-slider"
            min={MIN_ZOOM * 100}
            max={MAX_ZOOM * 100}
            value={isFit ? 100 : zoom * 100}
            onChange={(e) => setZoomLevel(parseInt(e.target.value) / 100)}
          />
          <button className="preview-toolbar__btn" onClick={zoomIn} title="Zoom in (+)">
            +
          </button>
          <span className="preview-toolbar__zoom-label">
            {isFit ? 'Fit' : `${Math.round(zoom * 100)}%`}
          </span>
          <button
            className={`preview-toolbar__btn ${isFit ? 'preview-toolbar__btn--active' : ''}`}
            onClick={fitToWindow}
            title="Fit to window (0)"
          >
            Fit
          </button>
          <button
            className={`preview-toolbar__btn ${!isFit && zoom === 1 ? 'preview-toolbar__btn--active' : ''}`}
            onClick={() => setZoomLevel(1)}
            title="100% (1)"
          >
            1:1
          </button>
        </div>

        <div className="preview-toolbar__group">
          <button
            className="preview-toolbar__btn"
            disabled={currentIndex <= 0}
            onClick={() => onNavigate(currentIndex - 1)}
            title="Previous (←)"
          >
            ◀ Prev
          </button>
          <span className="preview-toolbar__counter">
            {currentIndex + 1} / {files.length}
          </span>
          <button
            className="preview-toolbar__btn"
            disabled={currentIndex >= files.length - 1}
            onClick={() => onNavigate(currentIndex + 1)}
            title="Next (→)"
          >
            Next ▶
          </button>
        </div>
      </div>

      {/* Image area */}
      <div
        className="preview-canvas"
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        style={{ cursor: isPanning ? 'grabbing' : !isFit || zoom > 1 ? 'grab' : 'default' }}
      >
        {viewMode === 'split' && (
          <div className="preview-split" style={imageStyle}>
            <div
              className="preview-split__left"
              style={{ width: `${splitPosition}%` }}
            >
              {renderPlaceholder('negative')}
            </div>
            <div
              className="preview-split__right"
              style={{ width: `${100 - splitPosition}%` }}
            >
              {renderPlaceholder('positive')}
            </div>
            <div
              className="preview-split__divider"
              style={{ left: `${splitPosition}%` }}
              onMouseDown={(e) => {
                e.stopPropagation()
                setIsDraggingSplit(true)
              }}
            >
              <div className="preview-split__handle" />
            </div>
          </div>
        )}

        {viewMode === 'single' && (
          <div className="preview-single" style={imageStyle}>
            {renderPlaceholder('positive')}
          </div>
        )}

        {viewMode === 'overlay' && (
          <div className="preview-overlay-mode" style={imageStyle}>
            <div className="preview-overlay__back">
              {renderPlaceholder('negative')}
            </div>
            <div className="preview-overlay__front" style={{ opacity: 0.5 }}>
              {renderPlaceholder('positive')}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default PreviewPanel
