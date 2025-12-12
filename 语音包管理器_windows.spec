# -*- mode: python ; coding: utf-8 -*-
# Windows 打包配置文件
# 使用方法: pyinstaller 语音包管理器_windows.spec --noconfirm

from PyInstaller.utils.hooks import collect_all
import os

# 获取 ffmpeg 路径 (Windows 常见位置)
ffmpeg_paths = [
    r'C:\ffmpeg\bin\ffmpeg.exe',
    os.path.join(os.environ.get('ProgramFiles', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'ffmpeg', 'bin', 'ffmpeg.exe'),
]
ffprobe_paths = [
    r'C:\ffmpeg\bin\ffprobe.exe',
    os.path.join(os.environ.get('ProgramFiles', ''), 'ffmpeg', 'bin', 'ffprobe.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'ffmpeg', 'bin', 'ffprobe.exe'),
]

ffmpeg_exe = None
ffprobe_exe = None
for p in ffmpeg_paths:
    if os.path.exists(p):
        ffmpeg_exe = p
        break
for p in ffprobe_paths:
    if os.path.exists(p):
        ffprobe_exe = p
        break

datas = []
binaries = []

# 添加 ffmpeg (如果找到)
if ffmpeg_exe:
    binaries.append((ffmpeg_exe, '.'))
    print(f"找到 ffmpeg: {ffmpeg_exe}")
else:
    print("警告: 未找到 ffmpeg.exe，请确保系统已安装 ffmpeg 或手动指定路径")

if ffprobe_exe:
    binaries.append((ffprobe_exe, '.'))
    print(f"找到 ffprobe: {ffprobe_exe}")

hiddenimports = [
    'pilk', 'pilk._pilk', 'pilk.SilkDecoder', 'pilk.SilkEncoder',
    'pydub', 'pydub.utils', 'pydub.audio_segment',
    'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.QtMultimedia'
]

# 收集 pilk 的所有文件
tmp_ret = collect_all('pilk')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

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
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以指定 .ico 图标文件
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
