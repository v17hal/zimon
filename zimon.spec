# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ZIMON desktop app.

Build:  pyinstaller zimon.spec
Output: dist/ZIMON/ZIMON.exe  (one-folder)
        dist/ZIMON_Setup.exe  (optional — use NSIS/Inno Setup on the folder)
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all data files (QSS stylesheet, Arduino firmware, config)
added_files = [
    ('gui_v2/styles_v2.qss',       'gui_v2'),
    ('gui/styles.qss',              'gui'),
    ('config',                      'config'),
    ('arduino',                     'arduino'),
    ('version.py',                  '.'),
]

# Hidden imports that PyInstaller misses
hidden = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'cv2',
    'numpy',
    'serial',
    'serial.tools.list_ports',
    'sqlite3',
    'scipy',
    'PIL',
]

a = Analysis(
    ['main_v2.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pypylon', 'PySpin', 'pytest', 'black', 'flake8'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZIMON',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # No console window in production
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # Add path to .ico file here when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZIMON',
)
