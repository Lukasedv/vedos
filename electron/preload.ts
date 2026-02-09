import { contextBridge, ipcRenderer } from 'electron';
import type {
  FileInfo,
  ProcessingConfig,
  ProcessingStatus,
  AICorrectionParams,
} from '../src/types';

export interface VedosAPI {
  selectFiles: () => Promise<string[]>;
  importFiles: (filePaths: string[]) => Promise<FileInfo[]>;
  startProcessing: (config: ProcessingConfig) => Promise<{ job_id: string; status: string }>;
  getStatus: (jobId: string) => Promise<ProcessingStatus>;
  getPreview: (jobId: string) => Promise<{ job_id: string; preview_url: string | null; message: string }>;
  triggerAICorrection: (jobId: string) => Promise<AICorrectionParams>;
  onProgress: (callback: (progress: number, file: string) => void) => () => void;
  onFilesSelected: (callback: (files: string[]) => void) => () => void;
}

contextBridge.exposeInMainWorld('vedos', {
  selectFiles: () => ipcRenderer.invoke('select-files'),

  importFiles: (filePaths: string[]) => ipcRenderer.invoke('import-files', filePaths),

  startProcessing: (config: ProcessingConfig) => ipcRenderer.invoke('start-processing', config),

  getStatus: (jobId: string) => ipcRenderer.invoke('get-status', jobId),

  getPreview: (jobId: string) => ipcRenderer.invoke('get-preview', jobId),

  triggerAICorrection: (jobId: string) => ipcRenderer.invoke('trigger-ai-correction', jobId),

  onProgress: (callback: (progress: number, file: string) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, progress: number, file: string) => {
      callback(progress, file);
    };
    ipcRenderer.on('processing-progress', listener);
    return () => {
      ipcRenderer.removeListener('processing-progress', listener);
    };
  },

  onFilesSelected: (callback: (files: string[]) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, files: string[]) => {
      callback(files);
    };
    ipcRenderer.on('files-selected', listener);
    return () => {
      ipcRenderer.removeListener('files-selected', listener);
    };
  },
} satisfies VedosAPI);
