import { useState, useCallback, useRef } from 'react'
import { ImportedFile, FilmType, AIModel, MaskRegion } from '../types'

export type AppPhase = 'idle' | 'configuring' | 'processing' | 'complete'

export type FileProcessingStatus = 'queued' | 'processing' | 'done' | 'error'

export interface FileResult {
  id: string
  filename: string
  status: FileProcessingStatus
  error?: string
  currentStep?: string
}

export interface InversionParams {
  blackPoint: number
  whitePoint: number
  contrast: number
}

export interface ExportConfig {
  outputDir: string
  outputFormat: string
  namingPattern: string
  overwrite: boolean
}

export interface ProcessingSettings {
  filmType: FilmType
  maskRegion: MaskRegion | null
  maskMode: 'auto' | 'manual'
  inversion: InversionParams
  aiEnabled: boolean
  aiModel: AIModel
  aiRefine: boolean
}

export interface ProcessingState {
  phase: AppPhase
  progress: number
  currentFileIndex: number
  totalFiles: number
  fileResults: FileResult[]
  currentStep: string
  estimatedTimeRemaining: number | null
  settings: ProcessingSettings
  exportConfig: ExportConfig
}

const PROCESSING_STEPS = ['Reading RAW', 'Inverting', 'AI Analysis', 'Writing DNG']

const DEFAULT_SETTINGS: ProcessingSettings = {
  filmType: 'color_negative',
  maskRegion: null,
  maskMode: 'auto',
  inversion: { blackPoint: 0.1, whitePoint: 99.9, contrast: 1.0 },
  aiEnabled: true,
  aiModel: 'claude-sonnet-4.5',
  aiRefine: false,
}

const DEFAULT_EXPORT: ExportConfig = {
  outputDir: '',
  outputFormat: 'dng',
  namingPattern: '{original}_positive',
  overwrite: false,
}

export function useProcessing() {
  const [phase, setPhase] = useState<AppPhase>('idle')
  const [progress, setProgress] = useState(0)
  const [currentFileIndex, setCurrentFileIndex] = useState(0)
  const [fileResults, setFileResults] = useState<FileResult[]>([])
  const [currentStep, setCurrentStep] = useState('')
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<number | null>(null)
  const [settings, setSettings] = useState<ProcessingSettings>(DEFAULT_SETTINGS)
  const [exportConfig, setExportConfig] = useState<ExportConfig>(DEFAULT_EXPORT)
  const cancelRef = useRef(false)

  const openConfiguring = useCallback(() => {
    setPhase('configuring')
  }, [])

  const closeConfiguring = useCallback(() => {
    setPhase('idle')
  }, [])

  const updateSettings = useCallback((partial: Partial<ProcessingSettings>) => {
    setSettings((prev) => ({ ...prev, ...partial }))
  }, [])

  const updateInversion = useCallback((partial: Partial<InversionParams>) => {
    setSettings((prev) => ({
      ...prev,
      inversion: { ...prev.inversion, ...partial },
    }))
  }, [])

  const updateExportConfig = useCallback((partial: Partial<ExportConfig>) => {
    setExportConfig((prev) => ({ ...prev, ...partial }))
  }, [])

  const startProcessing = useCallback(
    async (files: ImportedFile[]) => {
      cancelRef.current = false
      const results: FileResult[] = files.map((f) => ({
        id: f.id,
        filename: f.filename,
        status: 'queued' as FileProcessingStatus,
      }))
      setFileResults(results)
      setProgress(0)
      setCurrentFileIndex(0)
      setPhase('processing')

      const totalFiles = files.length
      const msPerStep = 400
      const startTime = Date.now()

      for (let i = 0; i < totalFiles; i++) {
        if (cancelRef.current) break
        setCurrentFileIndex(i)

        const steps = settings.aiEnabled
          ? PROCESSING_STEPS
          : PROCESSING_STEPS.filter((s) => s !== 'AI Analysis')

        for (let s = 0; s < steps.length; s++) {
          if (cancelRef.current) break
          setCurrentStep(steps[s])
          setFileResults((prev) =>
            prev.map((r, idx) =>
              idx === i ? { ...r, status: 'processing', currentStep: steps[s] } : r
            )
          )

          await new Promise((resolve) => setTimeout(resolve, msPerStep))

          const completed = i * steps.length + s + 1
          const total = totalFiles * steps.length
          setProgress(Math.round((completed / total) * 100))

          const elapsed = Date.now() - startTime
          const rate = elapsed / completed
          const remaining = Math.round((rate * (total - completed)) / 1000)
          setEstimatedTimeRemaining(remaining)
        }

        if (!cancelRef.current) {
          // Simulate occasional errors for testing
          const hasError = Math.random() < 0.05
          setFileResults((prev) =>
            prev.map((r, idx) =>
              idx === i
                ? {
                    ...r,
                    status: hasError ? 'error' : 'done',
                    error: hasError ? 'Failed to read RAW data' : undefined,
                    currentStep: undefined,
                  }
                : r
            )
          )
        }
      }

      if (!cancelRef.current) {
        setProgress(100)
        setCurrentStep('')
        setEstimatedTimeRemaining(null)
        setPhase('complete')
      }
    },
    [settings.aiEnabled]
  )

  const cancelProcessing = useCallback(() => {
    cancelRef.current = true
    setPhase('idle')
    setProgress(0)
    setFileResults([])
    setCurrentStep('')
    setEstimatedTimeRemaining(null)
  }, [])

  const resetProcessing = useCallback(() => {
    setPhase('idle')
    setProgress(0)
    setCurrentFileIndex(0)
    setFileResults([])
    setCurrentStep('')
    setEstimatedTimeRemaining(null)
  }, [])

  return {
    phase,
    progress,
    currentFileIndex,
    totalFiles: fileResults.length,
    fileResults,
    currentStep,
    estimatedTimeRemaining,
    settings,
    exportConfig,
    openConfiguring,
    closeConfiguring,
    updateSettings,
    updateInversion,
    updateExportConfig,
    startProcessing,
    cancelProcessing,
    resetProcessing,
    setPhase,
  }
}
