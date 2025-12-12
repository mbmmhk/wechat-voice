#!/usr/bin/env python3
"""
将 plist 文件中的 SILK 音频数据转换为 MP3/WAV 文件

使用方法:
    python convert_plist_to_audio.py <plist文件路径> [输出目录] [格式]

依赖安装:
    pip install pilk pydub

注意: pydub 需要 ffmpeg，请确保系统已安装 ffmpeg:
    macOS: brew install ffmpeg
    Ubuntu: sudo apt install ffmpeg
"""

import plistlib
import base64
import os
import sys
import re
from pathlib import Path

def sanitize_filename(name: str, max_length: int = 50) -> str:
    """清理文件名，移除非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    if len(name) > max_length:
        name = name[:max_length]
    return name.strip() or "unnamed"

def convert_silk_to_audio(silk_data: bytes, output_path: str, output_format: str = "mp3"):
    """将 SILK 数据转换为音频文件"""
    try:
        import pilk
        from pydub import AudioSegment
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.silk', delete=False) as silk_file:
            silk_file.write(silk_data)
            silk_path = silk_file.name

        with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as pcm_file:
            pcm_path = pcm_file.name

        try:
            duration = pilk.decode(silk_path, pcm_path)
            audio = AudioSegment.from_raw(
                pcm_path,
                sample_width=2,
                frame_rate=24000,
                channels=1
            )
            audio.export(output_path, format=output_format)
            return True, duration
        finally:
            os.unlink(silk_path)
            os.unlink(pcm_path)

    except ImportError as e:
        return False, f"缺少依赖: {e}. 请运行: pip install pilk pydub"
    except Exception as e:
        return False, str(e)

def save_silk_raw(silk_data: bytes, output_path: str):
    """直接保存原始 SILK 文件"""
    with open(output_path, 'wb') as f:
        f.write(silk_data)
    return True

def convert_plist_to_audio(plist_path: str, output_dir: str = None, output_format: str = "mp3"):
    """将 plist 文件中的音频数据转换为音频文件"""
    plist_path = Path(plist_path)

    if not plist_path.exists():
        print(f"错误: 文件不存在 - {plist_path}")
        return

    if output_dir is None:
        output_dir = plist_path.parent / "audio_output"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在读取: {plist_path}")
    with open(plist_path, 'rb') as f:
        plist_data = plistlib.load(f)

    print(f"找到 {len(plist_data)} 个音频条目")
    print(f"输出目录: {output_dir}")
    print(f"输出格式: {output_format}")
    print("-" * 50)

    success_count = 0
    fail_count = 0

    for idx, (name, base64_data) in enumerate(plist_data.items(), 1):
        safe_name = sanitize_filename(name)

        try:
            audio_data = base64.b64decode(base64_data)

            if not audio_data.startswith(b'\x02#!SILK_V3'):
                print(f"[{idx}] 跳过 '{safe_name}' - 不是 SILK 格式")
                fail_count += 1
                continue

            if output_format == "silk":
                output_path = output_dir / f"{safe_name}.silk"
                save_silk_raw(audio_data, str(output_path))
                print(f"[{idx}] ✓ 已保存: {safe_name}.silk")
                success_count += 1
            else:
                output_path = output_dir / f"{safe_name}.{output_format}"
                success, result = convert_silk_to_audio(audio_data, str(output_path), output_format)

                if success:
                    print(f"[{idx}] ✓ 已转换: {safe_name}.{output_format} (时长: {result:.1f}ms)")
                    success_count += 1
                else:
                    print(f"[{idx}] ✗ 转换失败 '{safe_name}': {result}")
                    fail_count += 1

        except Exception as e:
            print(f"[{idx}] ✗ 处理失败 '{safe_name}': {e}")
            fail_count += 1

    print("-" * 50)
    print(f"完成! 成功: {success_count}, 失败: {fail_count}")
    print(f"输出目录: {output_dir}")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n示例:")
        print(f"  python {sys.argv[0]} 软妹怼人有点可爱.plist")
        print(f"  python {sys.argv[0]} 软妹怼人有点可爱.plist ./output mp3")
        print(f"  python {sys.argv[0]} 软妹怼人有点可爱.plist ./output silk")
        return

    plist_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    output_format = sys.argv[3] if len(sys.argv) > 3 else "mp3"

    if output_format not in ["mp3", "wav", "silk"]:
        print(f"不支持的格式: {output_format}")
        print("支持的格式: mp3, wav, silk")
        return

    convert_plist_to_audio(plist_path, output_dir, output_format)

if __name__ == "__main__":
    main()
