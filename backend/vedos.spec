# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for bundling the Vedos Python backend

a = Analysis(
    ['vedos/app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'rawpy',
        'numpy',
        'scipy',
        'PIL',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'pydantic',
        'vedos',
        'vedos.app',
        'vedos.models',
        'vedos.pipeline',
        'vedos.raw_reader',
        'vedos.inversion',
        'vedos.dng_writer',
        'vedos.ai_correction',
        'vedos.batch_engine',
        'vedos.job_store',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='vedos-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='vedos-backend',
)
