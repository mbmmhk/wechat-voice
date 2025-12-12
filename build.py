#!/usr/bin/env python3
"""
跨平台打包脚本 - 将语音包管理器打包为可执行文件

使用方法:
    python build.py

依赖安装:
    pip install pyinstaller

打包后的文件位置:
    macOS: dist/语音包管理器.app
    Windows: dist/语音包管理器.exe
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def install_pyinstaller():
    """安装 PyInstaller"""
    print("正在安装 PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

def find_ffmpeg():
    """查找 ffmpeg 和 ffprobe 路径"""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    return ffmpeg, ffprobe

def build():
    # 检查 PyInstaller
    try:
        import PyInstaller
    except ImportError:
        install_pyinstaller()

    system = platform.system()
    print(f"当前系统: {system}")

    # 查找 ffmpeg
    ffmpeg_path, ffprobe_path = find_ffmpeg()
    if ffmpeg_path:
        print(f"找到 ffmpeg: {ffmpeg_path}")
    else:
        print("⚠️ 未找到 ffmpeg，音频转换功能可能无法使用")

    # 基本参数
    app_name = "语音包管理器"
    main_script = "voice_manager.py"

    # PyInstaller 参数 - 使用 onedir 模式避免启动闪烁
    args = [
        "pyinstaller",
        "--name", app_name,
        "--windowed",  # 无控制台窗口
        "--clean",     # 清理临时文件
        "--noconfirm", # 不确认覆盖
        # 隐藏导入
        "--hidden-import", "pilk",
        "--hidden-import", "pilk._pilk",
        "--hidden-import", "pilk.SilkDecoder",
        "--hidden-import", "pilk.SilkEncoder",
        "--hidden-import", "pydub",
        "--hidden-import", "pydub.utils",
        "--hidden-import", "pydub.audio_segment",
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtMultimedia",
        # 收集所有 pilk 包的数据
        "--collect-all", "pilk",
    ]

    # 添加 ffmpeg 到打包
    if ffmpeg_path:
        if system == "Darwin":
            args.extend(["--add-binary", f"{ffmpeg_path}:./"])
        else:
            args.extend(["--add-binary", f"{ffmpeg_path};./"])

    if ffprobe_path:
        if system == "Darwin":
            args.extend(["--add-binary", f"{ffprobe_path}:./"])
        else:
            args.extend(["--add-binary", f"{ffprobe_path};./"])

    # macOS 特定设置
    if system == "Darwin":
        args.extend([
            "--osx-bundle-identifier", "com.voicemanager.app",
        ])
        # 如果有图标文件
        icon_path = Path("icon.icns")
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])

    # Windows 特定设置
    elif system == "Windows":
        # 如果有图标文件
        icon_path = Path("icon.ico")
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])

    args.append(main_script)

    print(f"执行命令: {' '.join(args)}")
    print("-" * 50)

    # 执行打包
    result = subprocess.run(args)

    if result.returncode == 0:
        print("-" * 50)
        print("✅ 打包成功!")
        if system == "Darwin":
            print(f"   应用位置: dist/{app_name}.app")
        else:
            print(f"   应用位置: dist/{app_name}/")
            print(f"   可执行文件: dist/{app_name}/{app_name}.exe")
        print("\n提示: 首次运行可能需要允许安全权限")
    else:
        print("❌ 打包失败")
        sys.exit(1)

if __name__ == "__main__":
    build()
