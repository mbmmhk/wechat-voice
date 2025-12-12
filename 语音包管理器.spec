# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = [('/opt/homebrew/bin/ffmpeg', './'), ('/opt/homebrew/bin/ffprobe', './')]
hiddenimports = ['pilk', 'pilk._pilk', 'pilk.SilkDecoder', 'pilk.SilkEncoder', 'pydub', 'pydub.utils', 'pydub.audio_segment', 'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.QtMultimedia']
tmp_ret = collect_all('pilk')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['voice_manager.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='语音包管理器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='语音包管理器',
)
app = BUNDLE(
    coll,
    name='语音包管理器.app',
    icon=None,
    bundle_identifier='com.voicemanager.app',
)
