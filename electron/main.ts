import { app, BrowserWindow, ipcMain, dialog, Menu, MenuItemConstructorOptions } from 'electron';
import { ChildProcess, spawn } from 'child_process';
import * as fs from 'fs';
import * as net from 'net';
import * as path from 'path';
import { ApiClient } from './api-client';
import type { ProcessingConfig } from '../src/types';

const isDev = !app.isPackaged;

let pythonProcess: ChildProcess | null = null;
let apiClient: ApiClient | null = null;

// --- Python backend lifecycle ---

function getPythonBackendPath(): { exe: string; args: string[]; cwd: string } {
  if (app.isPackaged) {
    const backendDir = path.join(process.resourcesPath, 'backend');
    const exeName = process.platform === 'win32' ? 'vedos-backend.exe' : 'vedos-backend';
    return {
      exe: path.join(backendDir, exeName),
      args: [],
      cwd: backendDir,
    };
  }
  // Dev mode: use venv Python
  const venvBin = process.platform === 'win32' ? 'Scripts' : 'bin';
  const venvPython = path.join(app.getAppPath(), 'backend', '.venv', venvBin, 'python');
  const pythonExe = fs.existsSync(venvPython) ? venvPython : 'python3';
  return {
    exe: pythonExe,
    args: ['-m', 'vedos.app'],
    cwd: path.join(app.getAppPath(), 'backend'),
  };
}

function getRandomPort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const addr = srv.address();
      if (addr && typeof addr === 'object') {
        const port = addr.port;
        srv.close(() => resolve(port));
      } else {
        srv.close(() => reject(new Error('Failed to get port')));
      }
    });
    srv.on('error', reject);
  });
}

async function waitForBackend(port: number, retries = 30, delayMs = 500): Promise<void> {
  const url = `http://localhost:${port}/health`;
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  throw new Error(`Backend did not become ready on port ${port} after ${retries} attempts`);
}

async function spawnBackend(): Promise<number> {
  const port = await getRandomPort();
  const backend = getPythonBackendPath();
  const allArgs = [...backend.args, '--port', String(port)];

  console.log(`[vedos] Starting backend: ${backend.exe} ${allArgs.join(' ')}`);

  pythonProcess = spawn(backend.exe, allArgs, {
    cwd: backend.cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  pythonProcess.stdout?.on('data', (d: Buffer) => console.log(`[python] ${d.toString().trimEnd()}`));
  pythonProcess.stderr?.on('data', (d: Buffer) => console.error(`[python] ${d.toString().trimEnd()}`));

  pythonProcess.on('exit', (code, signal) => {
    console.error(`[vedos] Python backend exited (code=${code}, signal=${signal})`);
    pythonProcess = null;
  });

  await waitForBackend(port);
  console.log(`[vedos] Backend ready on port ${port}`);
  return port;
}

function killBackend(): Promise<void> {
  return new Promise((resolve) => {
    if (!pythonProcess || pythonProcess.killed) {
      resolve();
      return;
    }

    const proc = pythonProcess;
    const forceKillTimer = setTimeout(() => {
      try { proc.kill('SIGKILL'); } catch { /* already dead */ }
      resolve();
    }, 5000);

    proc.on('exit', () => {
      clearTimeout(forceKillTimer);
      resolve();
    });

    proc.kill('SIGTERM');
  });
}

// --- Window ---

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'Vedos',
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
    win.webContents.openDevTools();
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  return win;
}

// --- Menu ---

function buildMenu(win: BrowserWindow): void {
  const template: MenuItemConstructorOptions[] = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Import RAW Files',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            const result = await dialog.showOpenDialog(win, {
              properties: ['openFile', 'multiSelections'],
              filters: [
                { name: 'RAW Files', extensions: ['dng', 'cr2', 'cr3', 'nef', 'arw', 'orf', 'raf', 'rw2', 'tif', 'tiff'] },
                { name: 'All Files', extensions: ['*'] },
              ],
            });
            if (!result.canceled && result.filePaths.length > 0) {
              win.webContents.send('files-selected', result.filePaths);
            }
          },
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { role: 'togglefullscreen' },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// --- IPC Handlers ---

const RAW_EXTENSIONS = ['arw', 'cr2', 'nef', 'raf', 'dng', 'orf', 'rw2'];

function setupIPC(): void {
  ipcMain.handle('select-files', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: 'RAW Files', extensions: RAW_EXTENSIONS },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    return result.canceled ? [] : result.filePaths;
  });

  ipcMain.handle('import-files', async (_event, filePaths: string[]) => {
    if (!apiClient) throw new Error('Backend not ready');
    return apiClient.importFiles(filePaths);
  });

  ipcMain.handle('start-processing', async (_event, config: ProcessingConfig) => {
    if (!apiClient) throw new Error('Backend not ready');
    return apiClient.startProcessing(config);
  });

  ipcMain.handle('get-status', async (_event, jobId: string) => {
    if (!apiClient) throw new Error('Backend not ready');
    return apiClient.getStatus(jobId);
  });

  ipcMain.handle('get-preview', async (_event, jobId: string) => {
    if (!apiClient) throw new Error('Backend not ready');
    return apiClient.getPreview(jobId);
  });

  ipcMain.handle('trigger-ai-correction', async (_event, jobId: string) => {
    if (!apiClient) throw new Error('Backend not ready');
    return apiClient.triggerAICorrection(jobId);
  });
}

// --- App lifecycle ---

app.whenReady().then(async () => {
  setupIPC();

  try {
    const port = await spawnBackend();
    apiClient = new ApiClient(port);
  } catch (err) {
    console.error('[vedos] Failed to start Python backend:', err);
  }

  const win = createWindow();
  buildMenu(win);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      const newWin = createWindow();
      buildMenu(newWin);
    }
  });
});

app.on('before-quit', () => {
  killBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
