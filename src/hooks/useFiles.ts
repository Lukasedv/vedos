import { useState, useCallback } from 'react'
import { ImportedFile, FilmType, AIModel, RAW_EXTENSIONS } from '../types'

function generateId(): string {
  return Math.random().toString(36).substring(2, 10)
}

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 ? filename.substring(dot).toLowerCase() : ''
}

function getFormat(filename: string): string {
  return getExtension(filename).replace('.', '').toUpperCase()
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export { formatFileSize }

export function useFiles() {
  const [files, setFiles] = useState<ImportedFile[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [filmType, setFilmType] = useState<FilmType>('color_negative')
  const [aiEnabled, setAiEnabled] = useState(false)
  const [aiModel, setAiModel] = useState<AIModel>('claude-sonnet-4.5')
  const [notification, setNotification] = useState<string | null>(null)

  const addFiles = useCallback((paths: string[]) => {
    const validPaths: string[] = []
    const rejected: string[] = []

    for (const p of paths) {
      const ext = getExtension(p)
      if (RAW_EXTENSIONS.includes(ext)) {
        validPaths.push(p)
      } else {
        rejected.push(p)
      }
    }

    if (rejected.length > 0) {
      setNotification(
        `${rejected.length} file(s) skipped — only RAW formats are supported.`
      )
      setTimeout(() => setNotification(null), 4000)
    }

    if (validPaths.length === 0) return

    const newFiles: ImportedFile[] = validPaths.map((p) => {
      const parts = p.replace(/\\/g, '/').split('/')
      const filename = parts[parts.length - 1]
      return {
        id: generateId(),
        path: p,
        filename,
        format: getFormat(filename),
        fileSize: Math.floor(Math.random() * 40_000_000) + 10_000_000, // placeholder
        status: 'imported',
      }
    })

    setFiles((prev) => {
      const existingPaths = new Set(prev.map((f) => f.path))
      const deduplicated = newFiles.filter((f) => !existingPaths.has(f.path))
      return [...prev, ...deduplicated]
    })
  }, [])

  const removeFiles = useCallback((ids: string[]) => {
    const toRemove = new Set(ids)
    setFiles((prev) => prev.filter((f) => !toRemove.has(f.id)))
    setSelectedIds((prev) => {
      const next = new Set(prev)
      for (const id of ids) next.delete(id)
      return next
    })
  }, [])

  const selectFile = useCallback((id: string) => {
    setSelectedIds(new Set([id]))
  }, [])

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const selectAll = useCallback(() => {
    setFiles((prev) => {
      setSelectedIds(new Set(prev.map((f) => f.id)))
      return prev
    })
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const openFileDialog = useCallback(async () => {
    try {
      const api = (window as Window & { vedos?: { selectFiles: () => Promise<string[]> } }).vedos
      if (api?.selectFiles) {
        const paths = await api.selectFiles()
        if (paths.length > 0) addFiles(paths)
      } else {
        // Dev fallback: simulate file selection
        addFiles([
          '/mock/photos/DSC00001.ARW',
          '/mock/photos/IMG_2345.CR2',
          '/mock/photos/DSCF6789.RAF',
        ])
      }
    } catch {
      // Dev fallback
      addFiles([
        '/mock/photos/DSC00001.ARW',
        '/mock/photos/IMG_2345.CR2',
        '/mock/photos/DSCF6789.RAF',
      ])
    }
  }, [addFiles])

  return {
    files,
    selectedIds,
    filmType,
    setFilmType,
    aiEnabled,
    setAiEnabled,
    aiModel,
    setAiModel,
    notification,
    addFiles,
    removeFiles,
    selectFile,
    toggleSelection,
    selectAll,
    clearSelection,
    openFileDialog,
  }
}
