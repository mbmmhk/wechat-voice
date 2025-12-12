#!/usr/bin/env python3
"""
语音包管理器 - 可视化管理 plist 音频文件

功能:
- 加载和显示 plist 中的所有音频
- 播放/试听音频
- 拖入新的音频/视频文件
- 编辑音频名称
- 删除音频
- 保存到 plist 文件

依赖安装:
    pip install PyQt6 pilk pydub

注意: 需要 ffmpeg:
    macOS: brew install ffmpeg
"""

import sys
import os
import plistlib
import base64
import tempfile
import re
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QFileDialog,
    QMessageBox, QLineEdit, QProgressBar, QMenu, QInputDialog,
    QStatusBar, QToolBar, QSplitter, QFrame, QStyle, QSplashScreen
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal, QMimeData, QTimer
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QKeySequence, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput


def setup_ffmpeg_path():
    """设置 ffmpeg 路径，支持打包后的应用"""
    if getattr(sys, 'frozen', False):
        # 打包后的应用
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            ffmpeg_path = os.path.join(base_path, 'ffmpeg')
            ffprobe_path = os.path.join(base_path, 'ffprobe')
        else:
            # macOS .app 结构
            base_path = os.path.dirname(sys.executable)
            app_path = os.path.dirname(os.path.dirname(base_path))
            frameworks_path = os.path.join(app_path, 'Frameworks')

            ffmpeg_path = os.path.join(frameworks_path, 'ffmpeg')
            ffprobe_path = os.path.join(frameworks_path, 'ffprobe')

            # 添加到 PATH
            if os.path.exists(frameworks_path):
                os.environ['PATH'] = frameworks_path + os.pathsep + os.environ.get('PATH', '')

        # 配置 pydub 使用打包的 ffmpeg
        if os.path.exists(ffmpeg_path):
            from pydub import AudioSegment
            AudioSegment.converter = ffmpeg_path
            if os.path.exists(ffprobe_path):
                AudioSegment.ffprobe = ffprobe_path

# 初始化时设置 ffmpeg 路径
setup_ffmpeg_path()


class AudioConverter:
    """音频转换工具类"""

    @staticmethod
    def silk_to_pcm(silk_data: bytes) -> Optional[str]:
        """SILK 转 PCM，返回临时文件路径"""
        try:
            import pilk

            with tempfile.NamedTemporaryFile(suffix='.silk', delete=False) as f:
                f.write(silk_data)
                silk_path = f.name

            pcm_path = silk_path.replace('.silk', '.pcm')
            pilk.decode(silk_path, pcm_path)
            os.unlink(silk_path)
            return pcm_path
        except Exception as e:
            print(f"SILK 转 PCM 失败: {e}")
            return None

    @staticmethod
    def silk_to_wav(silk_data: bytes) -> Optional[str]:
        """SILK 转 WAV，返回临时文件路径"""
        try:
            import pilk
            from pydub import AudioSegment

            with tempfile.NamedTemporaryFile(suffix='.silk', delete=False) as f:
                f.write(silk_data)
                silk_path = f.name

            pcm_path = silk_path.replace('.silk', '.pcm')
            pilk.decode(silk_path, pcm_path)

            audio = AudioSegment.from_raw(
                pcm_path,
                sample_width=2,
                frame_rate=24000,
                channels=1
            )

            wav_path = silk_path.replace('.silk', '.wav')
            audio.export(wav_path, format='wav')

            os.unlink(silk_path)
            os.unlink(pcm_path)
            return wav_path
        except Exception as e:
            print(f"SILK 转 WAV 失败: {e}")
            return None

    @staticmethod
    def get_ffmpeg_path() -> str:
        """获取 ffmpeg 路径"""
        import platform
        import shutil
        is_windows = platform.system() == 'Windows'
        is_macos = platform.system() == 'Darwin'
        ffmpeg_name = 'ffmpeg.exe' if is_windows else 'ffmpeg'

        # 打包后的应用：优先使用打包目录中的 ffmpeg
        if getattr(sys, 'frozen', False):
            print(f"[ffmpeg] 运行在打包模式, frozen={sys.frozen}")
            print(f"[ffmpeg] sys.executable={sys.executable}")

            if hasattr(sys, '_MEIPASS'):
                # PyInstaller onefile 模式
                print(f"[ffmpeg] _MEIPASS={sys._MEIPASS}")
                ffmpeg = os.path.join(sys._MEIPASS, ffmpeg_name)
                if os.path.exists(ffmpeg):
                    print(f"[ffmpeg] 找到 (onefile): {ffmpeg}")
                    return ffmpeg
            else:
                # PyInstaller onedir 模式
                base_path = os.path.dirname(sys.executable)
                print(f"[ffmpeg] onedir base_path={base_path}")

                if is_windows:
                    # Windows: exe 同目录或 _internal 目录
                    candidates = [
                        os.path.join(base_path, ffmpeg_name),
                        os.path.join(base_path, '_internal', ffmpeg_name),
                    ]
                    print(f"[ffmpeg] Windows 候选路径: {candidates}")
                    for ffmpeg in candidates:
                        if os.path.exists(ffmpeg):
                            print(f"[ffmpeg] 找到 (onedir): {ffmpeg}")
                            return ffmpeg
                    # 列出目录内容以便调试
                    print(f"[ffmpeg] 目录内容 ({base_path}):")
                    try:
                        for f in os.listdir(base_path)[:20]:
                            print(f"  - {f}")
                    except Exception as e:
                        print(f"  列目录失败: {e}")

                elif is_macos:
                    # macOS: Frameworks 目录
                    app_path = os.path.dirname(os.path.dirname(base_path))
                    ffmpeg = os.path.join(app_path, 'Frameworks', ffmpeg_name)
                    print(f"[ffmpeg] macOS Frameworks 路径: {ffmpeg}")
                    if os.path.exists(ffmpeg):
                        print(f"[ffmpeg] 找到 (Frameworks): {ffmpeg}")
                        return ffmpeg

        # 未打包或打包目录中没有 ffmpeg：使用系统安装的版本
        print("[ffmpeg] 尝试查找系统安装的 ffmpeg...")
        if is_windows:
            system_ffmpeg_paths = [
                r'C:\ProgramData\chocolatey\bin\ffmpeg.exe',  # Chocolatey
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'ffmpeg', 'bin', 'ffmpeg.exe'),
                os.path.join(os.environ.get('ProgramFiles', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
                os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'ffmpeg', 'bin', 'ffmpeg.exe'),
                r'C:\ffmpeg\bin\ffmpeg.exe',
            ]
        else:
            system_ffmpeg_paths = [
                '/opt/homebrew/bin/ffmpeg',  # Apple Silicon Homebrew
                '/usr/local/bin/ffmpeg',      # Intel Homebrew
                '/usr/bin/ffmpeg',            # 系统自带
            ]

        for path in system_ffmpeg_paths:
            if path and os.path.exists(path):
                print(f"[ffmpeg] 找到系统版本: {path}")
                return path

        # 最后尝试 PATH
        which_ffmpeg = shutil.which(ffmpeg_name)
        if which_ffmpeg:
            print(f"[ffmpeg] 在 PATH 中找到: {which_ffmpeg}")
            return which_ffmpeg

        print(f"[ffmpeg] 未找到，使用默认名称: {ffmpeg_name}")
        return ffmpeg_name  # 使用 PATH 中的 ffmpeg

    @staticmethod
    def audio_to_silk(input_path: str) -> Optional[bytes]:
        """将音频/视频文件转换为 SILK 格式"""
        try:
            import pilk
            import subprocess

            # 使用 subprocess 直接调用 ffmpeg，避免库冲突
            ffmpeg = AudioConverter.get_ffmpeg_path()
            print(f"使用 ffmpeg: {ffmpeg}")

            # 检查 ffmpeg 是否存在
            if not os.path.isabs(ffmpeg) or not os.path.exists(ffmpeg):
                # 如果不是绝对路径或文件不存在，尝试 which/where
                import shutil
                resolved = shutil.which(ffmpeg)
                if resolved:
                    print(f"[ffmpeg] 解析后路径: {resolved}")
                    ffmpeg = resolved
                else:
                    print(f"[ffmpeg] 错误: ffmpeg 未找到! 路径: {ffmpeg}")
                    print(f"[ffmpeg] 请确保已安装 ffmpeg 并添加到系统 PATH")
                    return None

            # 创建临时 PCM 文件
            with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as f:
                pcm_path = f.name

            # 使用 ffmpeg 转换为 PCM (16-bit, 24kHz, mono)
            print(f"正在转换音频: {input_path}")
            cmd = [
                ffmpeg, '-y', '-i', input_path,
                '-f', 's16le', '-ar', '24000', '-ac', '1',
                pcm_path
            ]

            # 设置环境变量，避免库冲突
            import platform
            env = os.environ.copy()

            if getattr(sys, 'frozen', False):
                if platform.system() == 'Darwin':
                    # macOS: 清除可能导致冲突的库路径
                    env.pop('DYLD_LIBRARY_PATH', None)
                    env.pop('DYLD_FALLBACK_LIBRARY_PATH', None)
                    env.pop('LD_LIBRARY_PATH', None)
                    # 设置 DYLD_LIBRARY_PATH 指向系统库，避免加载 PyQt6 的 FFmpeg 库
                    env['DYLD_LIBRARY_PATH'] = '/usr/lib:/usr/local/lib:/opt/homebrew/lib'
                elif platform.system() == 'Windows':
                    # Windows: 清理 PATH，移除可能包含 PyQt6 库的路径
                    base_path = os.path.dirname(sys.executable)
                    # 将 ffmpeg 所在目录添加到 PATH 最前面
                    ffmpeg_dir = os.path.dirname(ffmpeg)
                    if os.path.exists(ffmpeg_dir):
                        env['PATH'] = ffmpeg_dir + os.pathsep + env.get('PATH', '')

            # 运行 ffmpeg
            if platform.system() == 'Windows':
                # Windows 上使用 CREATE_NO_WINDOW 标志避免弹出命令行窗口
                creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
                result = subprocess.run(cmd, capture_output=True, text=True, env=env, creationflags=creation_flags)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                print(f"ffmpeg 错误: {result.stderr}")
                return None

            print(f"PCM 转换成功")

            # PCM 转 SILK
            silk_path = pcm_path.replace('.pcm', '.silk')
            print(f"正在转换为 SILK: {silk_path}")
            pilk.encode(pcm_path, silk_path, pcm_rate=24000, tencent=True)
            print(f"SILK 转换成功")

            # 读取 SILK 数据
            with open(silk_path, 'rb') as f:
                silk_data = f.read()

            # 清理临时文件
            os.unlink(pcm_path)
            os.unlink(silk_path)

            return silk_data
        except Exception as e:
            import traceback
            print(f"转换为 SILK 失败: {e}")
            traceback.print_exc()
            return None


class ConvertThread(QThread):
    """后台转换线程"""
    finished = pyqtSignal(str, bytes)  # name, silk_data
    error = pyqtSignal(str, str)  # name, error_message

    def __init__(self, file_path: str, name: str):
        super().__init__()
        self.file_path = file_path
        self.name = name

    def run(self):
        silk_data = AudioConverter.audio_to_silk(self.file_path)
        if silk_data:
            self.finished.emit(self.name, silk_data)
        else:
            self.error.emit(self.name, "转换失败")


class AudioListWidget(QListWidget):
    """支持拖放的音频列表"""
    files_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QListWidget {
                font-size: 14px;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #006cbd;
                color: white;
            }
            QListWidget::item:!selected:hover {
                background-color: #e5f3ff;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                files.append(file_path)
        if files:
            self.files_dropped.emit(files)


class VoiceManagerWindow(QMainWindow):
    """主窗口"""

    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac',
                         '.mp4', '.mov', '.avi', '.mkv', '.webm'}

    def __init__(self):
        super().__init__()
        self.plist_path: Optional[str] = None
        self.audio_data: Dict[str, str] = {}  # name -> base64 data
        self.temp_files: list = []
        self.modified = False
        self.current_playing: Optional[str] = None

        # 媒体播放器
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        self.setWindowTitle("语音包管理器")
        self.setMinimumSize(600, 500)
        self.resize(800, 600)

        # 创建菜单栏
        self.create_menu_bar()

        # 主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # 文件信息
        self.file_label = QLabel("未加载文件 - 拖入 plist 文件或点击「打开」")
        self.file_label.setStyleSheet("font-size: 13px; color: #666; padding: 5px;")
        layout.addWidget(self.file_label)

        # 音频列表
        self.audio_list = AudioListWidget()
        self.audio_list.files_dropped.connect(self.on_files_dropped)
        self.audio_list.itemDoubleClicked.connect(self.play_selected)
        self.audio_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.audio_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.audio_list)

        # 提示标签
        self.hint_label = QLabel("💡 双击播放 | 拖入音频/视频文件添加 | 右键更多操作")
        self.hint_label.setStyleSheet("font-size: 12px; color: #999; padding: 5px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        # 控制按钮
        btn_layout = QHBoxLayout()

        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self.play_selected)
        self.play_btn.setMinimumHeight(36)
        btn_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.clicked.connect(self.stop_playback)
        self.stop_btn.setMinimumHeight(36)
        btn_layout.addWidget(self.stop_btn)

        btn_layout.addStretch()

        self.add_btn = QPushButton("➕ 添加音频")
        self.add_btn.clicked.connect(self.add_audio_files)
        self.add_btn.setMinimumHeight(36)
        btn_layout.addWidget(self.add_btn)

        self.save_btn = QPushButton("💾 保存")
        self.save_btn.clicked.connect(self.save_plist)
        self.save_btn.setMinimumHeight(36)
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def create_menu_bar(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开 plist...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_plist)
        file_menu.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_plist)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.save_plist_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_action = QAction("导出所有音频...", self)
        export_action.triggered.connect(self.export_all_audio)
        file_menu.addAction(export_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")

        add_action = QAction("添加音频...", self)
        add_action.triggered.connect(self.add_audio_files)
        edit_menu.addAction(add_action)

        rename_action = QAction("重命名", self)
        rename_action.setShortcut(QKeySequence("F2"))
        rename_action.triggered.connect(self.rename_selected)
        edit_menu.addAction(rename_action)

        delete_action = QAction("删除", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.delete_selected)
        edit_menu.addAction(delete_action)


    def open_plist(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开 plist 文件", "", "Plist 文件 (*.plist)"
        )
        if file_path:
            self.load_plist(file_path)

    def load_plist(self, file_path: str):
        try:
            with open(file_path, 'rb') as f:
                self.audio_data = plistlib.load(f)

            self.plist_path = file_path
            self.modified = False
            self.update_ui()
            self.status_bar.showMessage(f"已加载 {len(self.audio_data)} 个音频")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载失败: {e}")

    def update_ui(self):
        self.audio_list.clear()

        for name in self.audio_data.keys():
            item = QListWidgetItem(f"🔊 {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.audio_list.addItem(item)

        if self.plist_path:
            title = f"语音包管理器 - {Path(self.plist_path).name}"
            if self.modified:
                title += " *"
            self.setWindowTitle(title)
            self.file_label.setText(f"📁 {self.plist_path} ({len(self.audio_data)} 个音频)")

        self.save_btn.setEnabled(self.modified)

    def play_selected(self):
        item = self.audio_list.currentItem()
        if not item:
            return

        name = item.data(Qt.ItemDataRole.UserRole)
        self.play_audio(name)

    def play_audio(self, name: str):
        if name not in self.audio_data:
            return

        self.stop_playback()

        try:
            # 解码 Base64
            audio_bytes = base64.b64decode(self.audio_data[name])

            # 检查是否是 SILK 格式
            if audio_bytes.startswith(b'\x02#!SILK_V3'):
                wav_path = AudioConverter.silk_to_wav(audio_bytes)
                if wav_path:
                    self.temp_files.append(wav_path)
                    self.player.setSource(QUrl.fromLocalFile(wav_path))
                    self.player.play()
                    self.current_playing = name
                    self.status_bar.showMessage(f"正在播放: {name}")
                else:
                    QMessageBox.warning(self, "播放失败", "无法解码 SILK 音频")
            else:
                # 尝试直接播放
                with tempfile.NamedTemporaryFile(suffix='.audio', delete=False) as f:
                    f.write(audio_bytes)
                    temp_path = f.name
                self.temp_files.append(temp_path)
                self.player.setSource(QUrl.fromLocalFile(temp_path))
                self.player.play()
                self.current_playing = name
                self.status_bar.showMessage(f"正在播放: {name}")

        except Exception as e:
            QMessageBox.warning(self, "播放失败", str(e))

    def stop_playback(self):
        self.player.stop()
        self.current_playing = None
        self.status_bar.showMessage("已停止")

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.current_playing = None
            self.status_bar.showMessage("播放完成")

    def add_audio_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频/视频文件", "",
            "媒体文件 (*.mp3 *.wav *.m4a *.aac *.ogg *.flac *.mp4 *.mov *.avi *.mkv *.webm);;所有文件 (*)"
        )
        if files:
            self.on_files_dropped(files)

    def on_files_dropped(self, files: list):
        # 检查是否有 plist 文件
        for f in files:
            if f.endswith('.plist'):
                self.load_plist(f)
                return

        # 筛选有效的音频/视频文件
        valid_files = []
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in self.SUPPORTED_FORMATS:
                valid_files.append(f)

        if not valid_files:
            QMessageBox.warning(self, "不支持的格式",
                f"支持的格式: {', '.join(self.SUPPORTED_FORMATS)}")
            return

        # 如果没有加载 plist，创建一个新的
        if not self.plist_path:
            self.audio_data = {}
            self.plist_path = None  # 新建的，还没有保存路径
            self.modified = True
            self.file_label.setText("📄 新建语音包（未保存）")
            self.setWindowTitle("语音包管理器 - 新建 *")

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(valid_files))
        self.progress_bar.setValue(0)

        self.convert_queue = valid_files.copy()
        self.convert_next()

    def convert_next(self):
        if not self.convert_queue:
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage("添加完成")
            return

        file_path = self.convert_queue.pop(0)
        default_name = Path(file_path).stem

        # 让用户自定义名称
        name, ok = QInputDialog.getText(
            self, "设置音频名称",
            f"文件: {Path(file_path).name}\n\n请输入音频名称:",
            text=default_name
        )

        if not ok or not name.strip():
            # 用户取消，跳过此文件，继续下一个
            self.progress_bar.setValue(self.progress_bar.value() + 1)
            self.convert_next()
            return

        name = name.strip()

        # 检查名称是否已存在
        if name in self.audio_data:
            reply = QMessageBox.question(
                self, "名称已存在",
                f"「{name}」已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.progress_bar.setValue(self.progress_bar.value() + 1)
                self.convert_next()
                return

        self.status_bar.showMessage(f"正在转换: {name}")

        self.convert_thread = ConvertThread(file_path, name)
        self.convert_thread.finished.connect(self.on_convert_finished)
        self.convert_thread.error.connect(self.on_convert_error)
        self.convert_thread.start()

    def on_convert_finished(self, name: str, silk_data: bytes):
        self.audio_data[name] = base64.b64encode(silk_data).decode('utf-8')
        self.modified = True
        self.update_ui()

        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.convert_next()

    def on_convert_error(self, name: str, error: str):
        QMessageBox.warning(self, "转换失败", f"{name}: {error}")
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.convert_next()

    def show_context_menu(self, pos):
        item = self.audio_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)

        play_action = menu.addAction("▶ 播放")
        play_action.triggered.connect(self.play_selected)

        menu.addSeparator()

        rename_action = menu.addAction("✏️ 重命名")
        rename_action.triggered.connect(self.rename_selected)

        export_action = menu.addAction("📤 导出")
        export_action.triggered.connect(self.export_selected)

        menu.addSeparator()

        delete_action = menu.addAction("🗑️ 删除")
        delete_action.triggered.connect(self.delete_selected)

        menu.exec(self.audio_list.mapToGlobal(pos))

    def rename_selected(self):
        item = self.audio_list.currentItem()
        if not item:
            return

        old_name = item.data(Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(
            self, "重命名", "输入新名称:", text=old_name
        )

        if ok and new_name and new_name != old_name:
            if new_name in self.audio_data:
                QMessageBox.warning(self, "错误", "名称已存在")
                return

            self.audio_data[new_name] = self.audio_data.pop(old_name)
            self.modified = True
            self.update_ui()

    def delete_selected(self):
        items = self.audio_list.selectedItems()
        if not items:
            return

        names = [item.data(Qt.ItemDataRole.UserRole) for item in items]
        count = len(names)

        if count == 1:
            msg = f"确定要删除「{names[0]}」吗？"
        else:
            msg = f"确定要删除选中的 {count} 个音频吗？"

        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for name in names:
                del self.audio_data[name]
            self.modified = True
            self.update_ui()
            self.status_bar.showMessage(f"已删除 {count} 个音频")

    def export_selected(self):
        items = self.audio_list.selectedItems()
        if not items:
            return

        names = [item.data(Qt.ItemDataRole.UserRole) for item in items]

        # 单个文件导出
        if len(names) == 1:
            name = names[0]
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出音频", f"{name}.mp3",
                "MP3 文件 (*.mp3);;WAV 文件 (*.wav);;SILK 文件 (*.silk)"
            )
            if file_path:
                self._export_single(name, file_path)
            return

        # 多个文件批量导出到目录
        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not output_dir:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(names))
        self.progress_bar.setValue(0)

        success = 0
        for name in names:
            safe_name = re.sub(r'[<>:"/\\|?*]', '', name)[:50]
            file_path = f"{output_dir}/{safe_name}.mp3"
            if self._export_single(name, file_path, show_message=False):
                success += 1
            self.progress_bar.setValue(self.progress_bar.value() + 1)

        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f"已导出 {success}/{len(names)} 个音频到 {output_dir}")

    def _export_single(self, name: str, file_path: str, show_message: bool = True) -> bool:
        """导出单个音频文件"""
        try:
            audio_bytes = base64.b64decode(self.audio_data[name])
            ext = Path(file_path).suffix.lower()

            if ext == '.silk':
                with open(file_path, 'wb') as f:
                    f.write(audio_bytes)
            else:
                if audio_bytes.startswith(b'\x02#!SILK_V3'):
                    from pydub import AudioSegment

                    wav_path = AudioConverter.silk_to_wav(audio_bytes)
                    if wav_path:
                        audio = AudioSegment.from_wav(wav_path)
                        audio.export(file_path, format=ext[1:])
                        os.unlink(wav_path)
                else:
                    with open(file_path, 'wb') as f:
                        f.write(audio_bytes)

            if show_message:
                self.status_bar.showMessage(f"已导出: {file_path}")
            return True
        except Exception as e:
            if show_message:
                QMessageBox.warning(self, "导出失败", str(e))
            return False

    def export_all_audio(self):
        if not self.audio_data:
            QMessageBox.information(self, "提示", "没有音频可导出")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not output_dir:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.audio_data))
        self.progress_bar.setValue(0)

        success = 0
        for name, data in self.audio_data.items():
            try:
                audio_bytes = base64.b64decode(data)
                safe_name = re.sub(r'[<>:"/\\|?*]', '', name)[:50]

                if audio_bytes.startswith(b'\x02#!SILK_V3'):
                    wav_path = AudioConverter.silk_to_wav(audio_bytes)
                    if wav_path:
                        from pydub import AudioSegment
                        audio = AudioSegment.from_wav(wav_path)
                        audio.export(f"{output_dir}/{safe_name}.mp3", format='mp3')
                        os.unlink(wav_path)
                        success += 1
                else:
                    with open(f"{output_dir}/{safe_name}.audio", 'wb') as f:
                        f.write(audio_bytes)
                    success += 1
            except Exception as e:
                print(f"导出失败 {name}: {e}")

            self.progress_bar.setValue(self.progress_bar.value() + 1)

        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "导出完成", f"成功导出 {success}/{len(self.audio_data)} 个音频")

    def save_plist(self):
        if not self.plist_path:
            self.save_plist_as()
            return

        try:
            # 检查文件是否只读，如果是则添加写入权限
            if os.path.exists(self.plist_path):
                current_mode = os.stat(self.plist_path).st_mode
                if not (current_mode & 0o200):  # 没有写入权限
                    os.chmod(self.plist_path, current_mode | 0o200)

            with open(self.plist_path, 'wb') as f:
                plistlib.dump(self.audio_data, f)

            self.modified = False
            self.update_ui()
            self.status_bar.showMessage("保存成功")
        except PermissionError:
            QMessageBox.critical(self, "保存失败", "没有写入权限，请检查文件权限或尝试「另存为」")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def save_plist_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "另存为", "", "Plist 文件 (*.plist)"
        )
        if file_path:
            self.plist_path = file_path
            self.save_plist()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.on_files_dropped(files)

    def closeEvent(self, event):
        if self.modified:
            reply = QMessageBox.question(
                self, "未保存的更改",
                "有未保存的更改，是否保存？",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Save:
                self.save_plist()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        # 清理临时文件
        for f in self.temp_files:
            try:
                os.unlink(f)
            except:
                pass

        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = VoiceManagerWindow()
    window.show()

    # 如果命令行传入了文件路径，直接加载
    if len(sys.argv) > 1:
        window.load_plist(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
