import React, { useCallback, useState } from 'react';
import './styles/app.css';
import { CorrectionResult } from './types';
import { useFiles } from './hooks/useFiles';
import { useProcessing } from './hooks/useProcessing';
import Toolbar from './components/Toolbar';
import ImportZone from './components/ImportZone';
import ThumbnailGrid from './components/ThumbnailGrid';
import StatusBar from './components/StatusBar';
import SettingsPanel from './components/SettingsPanel';
import ExportSettings from './components/ExportSettings';
import BatchProcessingUI from './components/BatchProcessingUI';
import PreviewPanel from './components/PreviewPanel';
import PreviewOverlay from './components/PreviewOverlay';
import AICorrectionPanel from './components/AICorrectionPanel';

const App: React.FC = () => {
  const {
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
    selectFile,
    toggleSelection,
    selectAll,
    clearSelection,
    openFileDialog,
  } = useFiles();

  const proc = useProcessing();

  const [previewFileId, setPreviewFileId] = useState<string | null>(null);
  const [maskSelecting, setMaskSelecting] = useState(false);
  const [correctionResults, setCorrectionResults] = useState<CorrectionResult[]>([]);
  const [correctionIndex, setCorrectionIndex] = useState(0);
  const showCorrectionReview = proc.phase === 'complete' && proc.settings.aiEnabled && correctionResults.length > 0;

  const previewFile = previewFileId ? files.find((f) => f.id === previewFileId) ?? null : null;
  const previewIndex = previewFile ? files.findIndex((f) => f.id === previewFile.id) : -1;

  const handlePreview = useCallback((id: string) => {
    setPreviewFileId(id);
  }, []);

  const handlePreviewBack = useCallback(() => {
    setPreviewFileId(null);
  }, []);

  const handlePreviewNavigate = useCallback(
    (index: number) => {
      if (index >= 0 && index < files.length) {
        setPreviewFileId(files[index].id);
      }
    },
    [files]
  );

  const hasFiles = files.length > 0;
  const showSettings = hasFiles && (proc.phase === 'idle' || proc.phase === 'configuring');
  const showExport = proc.phase === 'configuring';
  const showBatch = proc.phase === 'processing' || proc.phase === 'complete';

  // Sync toolbar controls → processing settings
  const handleFilmTypeChange = useCallback(
    (type: typeof filmType) => {
      setFilmType(type);
      proc.updateSettings({ filmType: type });
    },
    [setFilmType, proc.updateSettings]
  );

  const handleAiToggle = useCallback(
    (enabled: boolean) => {
      setAiEnabled(enabled);
      proc.updateSettings({ aiEnabled: enabled });
    },
    [setAiEnabled, proc.updateSettings]
  );

  const handleAiModelChange = useCallback(
    (model: typeof aiModel) => {
      setAiModel(model);
      proc.updateSettings({ aiModel: model });
    },
    [setAiModel, proc.updateSettings]
  );

  const handleProcessSelected = useCallback(() => {
    proc.openConfiguring();
  }, [proc.openConfiguring]);

  const handleStartProcessing = useCallback(() => {
    const selected = files.filter((f) => selectedIds.has(f.id));
    if (selected.length > 0) proc.startProcessing(selected);
  }, [files, selectedIds, proc.startProcessing]);

  const handleOpenOutputFolder = useCallback(() => {
    try {
      const api = (window as Window & { vedos?: { openPath: (p: string) => void } }).vedos;
      if (api?.openPath && proc.exportConfig.outputDir) {
        api.openPath(proc.exportConfig.outputDir);
      }
    } catch {
      // Dev fallback
    }
  }, [proc.exportConfig.outputDir]);

  // AI Correction review handlers
  const handleCorrectionAccept = useCallback((_fileIndex: number) => {
    // Move to next unreviewed file or close
    if (correctionIndex < correctionResults.length - 1) {
      setCorrectionIndex(correctionIndex + 1);
    }
  }, [correctionIndex, correctionResults.length]);

  const handleCorrectionReject = useCallback((fileIndex: number) => {
    setCorrectionResults((prev) => prev.filter((c) => c.fileIndex !== fileIndex));
    if (correctionIndex >= correctionResults.length - 1 && correctionIndex > 0) {
      setCorrectionIndex(correctionIndex - 1);
    }
  }, [correctionIndex, correctionResults.length]);

  const handleCorrectionReanalyze = useCallback((_fileIndex: number) => {
    // Placeholder — would trigger a new AI pass via the backend
  }, []);

  const handleApplyManual = useCallback(
    (_fileIndex: number, _params: { white_balance_shift: number; tint_shift: number; exposure_compensation: number; saturation_adjustment: number }) => {
      // Placeholder — would POST to /api/corrections/{job_id}/{file_index}
    },
    []
  );

  const handleAcceptAll = useCallback(() => {
    setCorrectionResults([]);
    setCorrectionIndex(0);
  }, []);

  const handleCloseCorrectionReview = useCallback(() => {
    setCorrectionResults([]);
    setCorrectionIndex(0);
  }, []);

  return (
    <>
      <Toolbar
        filmType={filmType}
        onFilmTypeChange={handleFilmTypeChange}
        aiEnabled={aiEnabled}
        onAiToggle={handleAiToggle}
        aiModel={aiModel}
        onAiModelChange={handleAiModelChange}
        selectedCount={selectedIds.size}
        onProcessSelected={handleProcessSelected}
      />
      <div className="main-area">
        <div className="main-content">
          {previewFile ? (
            <PreviewPanel
              file={previewFile}
              filmType={filmType}
              files={files}
              currentIndex={previewIndex}
              onNavigate={handlePreviewNavigate}
              onBack={handlePreviewBack}
              onSelectMaskRegion={() => setMaskSelecting(true)}
            />
          ) : hasFiles ? (
            <>
              <ImportZone hasFiles onFilesAdded={addFiles} onBrowse={openFileDialog} />
              <ThumbnailGrid
                files={files}
                selectedIds={selectedIds}
                onSelect={selectFile}
                onToggle={toggleSelection}
                onSelectAll={selectAll}
                onClearSelection={clearSelection}
                onPreview={handlePreview}
              />
            </>
          ) : (
            <ImportZone hasFiles={false} onFilesAdded={addFiles} onBrowse={openFileDialog} />
          )}
        </div>
        {showSettings && (
          <SettingsPanel
            settings={proc.settings}
            onUpdateSettings={proc.updateSettings}
            onUpdateInversion={proc.updateInversion}
          />
        )}
      </div>
      <StatusBar
        fileCount={files.length}
        selectedCount={selectedIds.size}
      />
      {notification && <div className="notification">{notification}</div>}

      {showExport && (
        <ExportSettings
          config={proc.exportConfig}
          onUpdate={proc.updateExportConfig}
          selectedCount={selectedIds.size}
          onStartProcessing={handleStartProcessing}
          onCancel={proc.closeConfiguring}
        />
      )}

      {showBatch && (
        <BatchProcessingUI
          progress={proc.progress}
          currentFileIndex={proc.currentFileIndex}
          totalFiles={proc.totalFiles}
          fileResults={proc.fileResults}
          currentStep={proc.currentStep}
          estimatedTimeRemaining={proc.estimatedTimeRemaining}
          isComplete={proc.phase === 'complete'}
          onCancel={proc.cancelProcessing}
          onReset={proc.resetProcessing}
          onOpenOutputFolder={handleOpenOutputFolder}
        />
      )}

      {showCorrectionReview && (
        <AICorrectionPanel
          corrections={correctionResults}
          currentIndex={correctionIndex}
          onNavigate={setCorrectionIndex}
          onAccept={handleCorrectionAccept}
          onReject={handleCorrectionReject}
          onReanalyze={handleCorrectionReanalyze}
          onApplyManual={handleApplyManual}
          onAcceptAll={handleAcceptAll}
          onClose={handleCloseCorrectionReview}
        />
      )}

      {maskSelecting && (
        <PreviewOverlay
          onConfirm={(region) => {
            proc.updateSettings({ maskRegion: region, maskMode: 'manual' });
            setMaskSelecting(false);
          }}
          onCancel={() => setMaskSelecting(false)}
        />
      )}
    </>
  );
};

export default App;
