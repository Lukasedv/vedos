/// <reference types="vite/client" />

interface ProcessingStatus {
  status: string;
  progress: number;
  currentFile: string | null;
}

interface ProcessingResult {
  success: boolean;
  jobId: string;
}

interface VedosAPI {
  selectFiles: () => Promise<string[]>;
  getProcessingStatus: () => Promise<ProcessingStatus>;
  startProcessing: (files: string[], options: Record<string, unknown>) => Promise<ProcessingResult>;
  onProgress: (callback: (progress: number, file: string) => void) => () => void;
  onFilesSelected: (callback: (files: string[]) => void) => () => void;
}

declare global {
  interface Window {
    vedos: VedosAPI;
  }
}
