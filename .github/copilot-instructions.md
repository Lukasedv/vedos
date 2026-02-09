# Copilot Instructions for Vedos

## Build & Run Commands

```bash
# Frontend + Electron dev (requires display)
npm run dev

# TypeScript type checking (both React and Electron configs)
npm run typecheck

# Build React frontend only
npm run build:renderer

# Build Electron main process only
npm run build:electron

# Build everything (React + Electron + Python backend via PyInstaller)
npm run build:all

# Package for distribution
npm run package          # all platforms
npm run package:win      # Windows NSIS installer
npm run package:mac      # macOS DMG
```

```bash
# Backend tests
cd backend
.venv/bin/python -m pytest                              # all tests
.venv/bin/python -m pytest tests/test_inversion.py      # single file
.venv/bin/python -m pytest tests/test_inversion.py::TestInvertColorNegative::test_output_dtype -v  # single test

# Run the Python backend standalone (for API testing)
cd backend && .venv/bin/python -m vedos.app --port 8765
```

## Architecture

Vedos is a **three-layer Electron app** that converts scanned film negatives to positive DNG files:

```
React/TypeScript UI (Vite, port 5173)
    ↕ Electron IPC (contextBridge)
Electron main process (Node.js)
    ↕ HTTP fetch (localhost, random port)
Python FastAPI backend (uvicorn)
```

**Electron spawns Python** — `electron/main.ts` finds the Python binary (`.venv/bin/python` in dev, PyInstaller bundle in production), starts FastAPI on a random port, and polls `/health` until ready. On quit, it sends SIGTERM → SIGKILL after 5s.

**IPC chain** — The renderer never calls the backend directly. All API calls flow: React component → `window.vedos.*` (preload) → `ipcRenderer.invoke` → `ipcMain` handler → `ApiClient` fetch → FastAPI endpoint.

**Processing pipeline** — A single file flows through: `raw_reader.read_raw()` → `inversion.invert_color_negative()` or `invert_bw_negative()` → optionally `ai_correction.CopilotColorAnalyzer.analyze_image()` + `apply_corrections()` → `dng_writer.write_dng()`. This is orchestrated by `pipeline.process_file()`, called in a loop by `batch_engine.BatchProcessor`.

**AI color correction** — Uses the GitHub Copilot SDK (`from copilot import CopilotClient`) to send a JPEG preview to a vision model (claude-sonnet-4.5 or haiku-4.5). The model returns structured JSON with correction parameters (WB, tint, exposure, per-channel curves, saturation). The `ANALYSIS_PROMPT` in `ai_correction.py` is carefully crafted — edit it with care.

## Key Conventions

### TypeScript

- Two tsconfig files: `tsconfig.json` (React, ESNext modules, `@/` path alias) and `tsconfig.electron.json` (Electron main process, CommonJS output to `dist-electron/`). Electron config imports `src/types.ts` for shared type definitions.
- The preload script (`electron/preload.ts`) defines the `window.vedos` API contract. Any new backend endpoint needs: FastAPI route → `ApiClient` method → `ipcMain` handler → preload exposure → TypeScript type.
- Frontend hooks `useFiles` and `useProcessing` currently **mock API calls** with dev fallbacks when `window.vedos` isn't available (non-Electron context). Real IPC calls go through the preload bridge.

### Python Backend

- All image data flows as `np.ndarray` with shape `(H, W, 3)` and dtype `uint16` (16-bit linear RGB, range 0–65535). Never convert to 8-bit mid-pipeline.
- Inversion operates in **log-density space** (`-log10`), not linear space. This is deliberate — film has a logarithmic response curve.
- The `models.py` Pydantic models mirror `src/types.ts` interfaces. Keep them in sync when adding fields.
- FastAPI app accepts `--port` as a CLI argument via `argparse`. Entry point is `python -m vedos.app`.
- `job_store.py` is an in-memory dict — jobs are lost on restart. This is intentional for a desktop app.

### DNG Output

- Output is **Linear DNG** (demosaiced RGB stored as TIFF with DNG tags). Lightroom treats this as RAW with full editing sliders.
- Uses `tifffile` with adobe_deflate compression and 256×256 tiles.
- The sRGB-to-XYZ D65 color matrix is hardcoded in `dng_writer.py`. For custom camera profiles, pass a `color_matrix` parameter.

### AI Correction JSON Contract

The AI model must return exactly this JSON shape (enforced by `parse_correction_response()`):
```json
{
  "white_balance_shift_kelvin": [-3000, +3000],
  "tint_shift": [-50, +50],
  "exposure_compensation": [-2.0, +2.0],
  "channel_curves": { "red/green/blue": { "shadows/midtones/highlights": [-50, +50] } },
  "saturation_adjustment": [-50, +50],
  "analysis_notes": "string"
}
```
The parser handles markdown fences and surrounding text, and clamps all values to valid ranges.
