# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Deadlock Discord Rich Presence.

Build with:
    pyinstaller deadlock_rpc.spec

Output will be in dist/DeadlockRPC/DeadlockRPC.exe (one-folder mode)
or use --onefile in the spec below for a single .exe.
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['deadlock_rpc.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Optional: uncomment if you have an assets/ folder with icon.ico/icon.png
        # ('assets/*', 'assets'),
    ],
    hiddenimports=[
        'pystray._win32' if sys.platform == 'win32' else 'pystray._xorg',
        'PIL._tkinter_finder',
        'flask',
        'pypresence',
        'engineio.async_drivers.threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email', 'xml', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DeadlockRPC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # ← No console window! Tray only.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # If you have a proper .ico file, set it here:
    # icon='assets/icon.ico',
)
