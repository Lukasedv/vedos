/**
 * Typed wrapper around fetch calls to the Python backend.
 */

import type {
  FileInfo,
  ProcessingConfig,
  ProcessingStatus,
  AICorrectionParams,
} from '../src/types';

export class ApiClient {
  private baseUrl: string;

  constructor(port: number) {
    this.baseUrl = `http://localhost:${port}`;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    let res: Response;
    try {
      res = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        signal: AbortSignal.timeout(30_000),
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Backend request failed (${path}): ${msg}`);
    }

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`Backend error ${res.status} on ${path}: ${body}`);
    }

    return res.json() as Promise<T>;
  }

  async healthCheck(): Promise<{ status: string; version: string }> {
    return this.request('/health');
  }

  async importFiles(filePaths: string[]): Promise<FileInfo[]> {
    return this.request<FileInfo[]>('/api/import', {
      method: 'POST',
      body: JSON.stringify(filePaths),
    });
  }

  async startProcessing(config: ProcessingConfig): Promise<{ job_id: string; status: string }> {
    return this.request('/api/process', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getStatus(jobId: string): Promise<ProcessingStatus> {
    return this.request<ProcessingStatus>(`/api/process/${encodeURIComponent(jobId)}/status`);
  }

  async getPreview(jobId: string): Promise<{ job_id: string; preview_url: string | null; message: string }> {
    return this.request(`/api/preview/${encodeURIComponent(jobId)}`);
  }

  async triggerAICorrection(jobId: string): Promise<AICorrectionParams> {
    return this.request<AICorrectionParams>(`/api/ai-correct?job_id=${encodeURIComponent(jobId)}`, {
      method: 'POST',
    });
  }
}
