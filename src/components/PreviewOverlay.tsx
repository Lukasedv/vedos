import React, { useState, useCallback, useRef } from 'react'
import { MaskRegion } from '../types'

interface PreviewOverlayProps {
  onConfirm: (region: MaskRegion) => void
  onCancel: () => void
}

const PreviewOverlay: React.FC<PreviewOverlayProps> = ({ onConfirm, onCancel }) => {
  const [region, setRegion] = useState<MaskRegion | null>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [startPoint, setStartPoint] = useState({ x: 0, y: 0 })
  const overlayRef = useRef<HTMLDivElement>(null)

  const getRelativeCoords = useCallback(
    (e: React.MouseEvent) => {
      if (!overlayRef.current) return { x: 0, y: 0 }
      const rect = overlayRef.current.getBoundingClientRect()
      return {
        x: Math.round(((e.clientX - rect.left) / rect.width) * 6000),
        y: Math.round(((e.clientY - rect.top) / rect.height) * 4000),
      }
    },
    []
  )

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      const coords = getRelativeCoords(e)
      setStartPoint(coords)
      setIsDrawing(true)
      setRegion(null)
    },
    [getRelativeCoords]
  )

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return
      const coords = getRelativeCoords(e)
      setRegion({
        x: Math.min(startPoint.x, coords.x),
        y: Math.min(startPoint.y, coords.y),
        w: Math.abs(coords.x - startPoint.x),
        h: Math.abs(coords.y - startPoint.y),
      })
    },
    [isDrawing, startPoint, getRelativeCoords]
  )

  const handleMouseUp = useCallback(() => {
    setIsDrawing(false)
  }, [])

  const rectStyle = region && overlayRef.current
    ? {
        left: `${(region.x / 6000) * 100}%`,
        top: `${(region.y / 4000) * 100}%`,
        width: `${(region.w / 6000) * 100}%`,
        height: `${(region.h / 4000) * 100}%`,
      }
    : undefined

  return (
    <div className="mask-overlay">
      <div className="mask-overlay__header">
        <span className="mask-overlay__title">Select Mask Region</span>
        <span className="mask-overlay__hint">Click and drag to select the unexposed film border</span>
      </div>
      <div
        className="mask-overlay__canvas"
        ref={overlayRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: 'crosshair' }}
      >
        <div
          className="mask-overlay__placeholder"
          style={{
            background: 'linear-gradient(135deg, #3d2a1a 0%, #5a3a1e 50%, #3d2a1a 100%)',
          }}
        />
        {region && rectStyle && (
          <div className="mask-overlay__rect" style={rectStyle}>
            <span className="mask-overlay__coords">
              {region.x}, {region.y} — {region.w}×{region.h}
            </span>
          </div>
        )}
      </div>
      <div className="mask-overlay__actions">
        {region && (
          <span className="mask-overlay__region-info">
            Region: x={region.x} y={region.y} w={region.w} h={region.h}
          </span>
        )}
        <div className="mask-overlay__buttons">
          <button className="mask-overlay__btn mask-overlay__btn--cancel" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="mask-overlay__btn mask-overlay__btn--confirm"
            disabled={!region || region.w < 10 || region.h < 10}
            onClick={() => region && onConfirm(region)}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}

export default PreviewOverlay
