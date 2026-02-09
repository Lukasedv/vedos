/** Mirrors Python Pydantic models from vedos.models */

export type FilmType = 'color_negative' | 'bw_negative';

export type AIModel = 'claude-sonnet-4.5' | 'claude-haiku-4.5';

export const RAW_EXTENSIONS = [
  '.arw', '.cr2', '.nef', '.raf', '.dng', '.orf', '.rw2', '.pef', '.srw',
];

export interface ImportedFile {
  id: string;
  path: string;
  filename: string;
  format: string;
  fileSize: number;
  thumbnailUrl?: string;
  status: 'imported' | 'processing' | 'done' | 'error';
}

export interface MaskRegion {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface FileInfo {
  path: string;
  filename: string;
  format: string;
  width: number;
  height: number;
  file_size: number;
}

export interface ProcessingConfig {
  files: string[];
  film_type?: FilmType;
  mask_region?: MaskRegion | null;
  ai_correction?: boolean;
  ai_model?: AIModel;
}

export interface ProcessingStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'complete' | 'error';
  progress: number;
  current_file?: string | null;
  total_files: number;
  completed_files: number;
  errors: string[];
}

export interface ChannelCurve {
  shadows: number;
  midtones: number;
  highlights: number;
}

export interface CurvesAdjustment {
  r: ChannelCurve;
  g: ChannelCurve;
  b: ChannelCurve;
}

export interface AICorrectionParams {
  white_balance_shift: number;
  tint_shift: number;
  exposure_compensation: number;
  curves: CurvesAdjustment;
  saturation_adjustment?: number;
  analysis_notes?: string;
}

export interface CorrectionResult {
  fileIndex: number;
  filename: string;
  corrections: AICorrectionParams;
  analysisNotes: string;
  beforePreviewUrl: string;
  afterPreviewUrl: string;
}
