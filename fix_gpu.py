#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU兼容性修复工具
下载兼容的FFmpeg版本并配置GPU加速
"""

import os
import sys
import time
import shutil
import zipfile
import logging
import requests
import subprocess
from pathlib import Path
from tqdm import tqdm

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加src目录到路径
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

# 兼容版本FFmpeg的下载链接
FFMPEG_URL = "https://github.com/GyanD/codexffmpeg/releases/download/5.1.2/ffmpeg-5.1.2-essentials_build.zip"

def download_ffmpeg(url, dest_dir):
    """
    下载FFmpeg
    
    Args:
        url: 下载地址
        dest_dir: 目标目录
    """
    print(f"正在下载兼容版本的FFmpeg...")
    dest_dir = Path(dest_dir)
    zip_path = dest_dir / "ffmpeg.zip"
    
    # 创建目录
    dest_dir.mkdir(exist_ok=True, parents=True)
    
    # 下载文件
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(zip_path, 'wb') as f, tqdm(
        desc="下载进度",
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as pbar:
        for data in response.iter_content(chunk_size=4096):
            pbar.update(len(data))
            f.write(data)
    
    print(f"下载完成! 文件保存在: {zip_path}")
    return zip_path

def extract_ffmpeg(zip_path, extract_dir):
    """
    解压FFmpeg
    
    Args:
        zip_path: 压缩包路径
        extract_dir: 解压目录
    """
    print("正在解压FFmpeg...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 获取压缩包中的顶级目录
        top_dirs = {item.split('/')[0] for item in zip_ref.namelist() if '/' in item}
        if len(top_dirs) == 1:
            top_dir = top_dirs.pop()
            
            # 解压所有文件
            zip_ref.extractall(extract_dir)
            
            # 移动bin目录中的文件到根目录
            bin_dir = Path(extract_dir) / top_dir / "bin"
            if bin_dir.exists():
                for file in bin_dir.glob("*"):
                    # 将ffmpeg.exe等文件移动到提取目录的根目录
                    target_path = Path(extract_dir) / file.name
                    shutil.move(str(file), str(target_path))
                    print(f"移动 {file.name} 到 {target_path}")
            
            # 删除解压后的原始目录结构
            shutil.rmtree(Path(extract_dir) / top_dir)
        else:
            # 直接解压所有文件
            zip_ref.extractall(extract_dir)
    
    # 验证提取是否成功
    ffmpeg_exe = Path(extract_dir) / "ffmpeg.exe"
    if ffmpeg_exe.exists():
        print(f"FFmpeg成功解压到: {ffmpeg_exe}")
        return str(ffmpeg_exe)
    else:
        print("未能找到解压后的ffmpeg.exe，尝试寻找...")
        for file in Path(extract_dir).glob("**/ffmpeg.exe"):
            print(f"找到FFmpeg: {file}")
            return str(file)
        
        print("错误: 未找到ffmpeg.exe!")
        return None

def test_ffmpeg(ffmpeg_path):
    """
    测试FFmpeg
    
    Args:
        ffmpeg_path: FFmpeg路径
    """
    print(f"正在测试FFmpeg: {ffmpeg_path}")
    try:
        cmd = [ffmpeg_path, "-version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        
        if "ffmpeg version" in result.stdout:
            print("FFmpeg测试成功!")
            return True
        else:
            print("FFmpeg测试失败!")
            return False
    except Exception as e:
        print(f"测试FFmpeg时出错: {e}")
        return False

def configure_ffmpeg_path(ffmpeg_path):
    """
    配置FFmpeg路径
    
    Args:
        ffmpeg_path: FFmpeg路径
    """
    print(f"正在配置FFmpeg路径: {ffmpeg_path}")
    try:
        with open("ffmpeg_path.txt", "w") as f:
            f.write(ffmpeg_path)
        print("FFmpeg路径配置成功!")
        return True
    except Exception as e:
        print(f"配置FFmpeg路径时出错: {e}")
        return False

def configure_gpu():
    """配置GPU加速"""
    print("正在配置GPU加速...")
    
    try:
        # 导入GPU配置模块
        from hardware.gpu_config import GPUConfig
        from hardware.system_analyzer import SystemAnalyzer
        
        # 检测GPU
        analyzer = SystemAnalyzer()
        system_info = analyzer.analyze()
        gpu_info = system_info.get('gpu', {})
        
        if not gpu_info.get('available', False):
            print("未检测到可用GPU!")
            return False
        
        print(f"检测到GPU: {gpu_info.get('primary_gpu', '未知')} ({gpu_info.get('primary_vendor', '未知')})")
        
        # 配置GPU
        gpu_config = GPUConfig()
        gpu_config.config['use_hardware_acceleration'] = True
        gpu_config.config['encoder'] = 'h264_nvenc'
        gpu_config.config['decoder'] = 'h264_cuvid'
        gpu_config.config['encoding_preset'] = 'p2'
        gpu_config.config['detected_gpu'] = gpu_info.get('primary_gpu', 'NVIDIA GPU')
        gpu_config.config['detected_vendor'] = gpu_info.get('primary_vendor', 'NVIDIA')
        gpu_config._save_config()
        
        print("GPU配置成功!")
        return True
    except Exception as e:
        print(f"配置GPU时出错: {e}")
        return False

def test_gpu_encoding(ffmpeg_path):
    """
    测试GPU编码
    
    Args:
        ffmpeg_path: FFmpeg路径
    """
    print("正在测试GPU编码能力...")
    
    # 创建测试目录
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    # 创建测试视频
    test_input = temp_dir / "test_input.mp4"
    if not test_input.exists():
        print("正在生成测试视频...")
        cmd = [
            ffmpeg_path, "-y", "-f", "lavfi", "-i", 
            "testsrc=duration=5:size=1280x720:rate=30", 
            "-c:v", "libx264", "-crf", "23", str(test_input)
        ]
        subprocess.run(cmd, capture_output=True)
    
    # 测试GPU编码
    test_output = temp_dir / "test_output_gpu.mp4"
    cmd = [
        ffmpeg_path, "-y", "-i", str(test_input),
        "-c:v", "h264_nvenc", 
        "-preset", "p2",
        "-b:v", "5000k",
        str(test_output)
    ]
    
    print(f"GPU编码测试命令: {' '.join(cmd)}")
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    encode_time = time.time() - start_time
    
    if result.returncode == 0 and test_output.exists():
        print(f"GPU编码测试成功! 用时: {encode_time:.2f}秒")
        print(f"输出文件: {test_output}")
        
        file_size = os.path.getsize(test_output) / (1024 * 1024)  # MB
        print(f"输出文件大小: {file_size:.2f} MB")
        return True
    else:
        print("GPU编码测试失败!")
        print(f"错误输出: {result.stderr}")
        return False

def main():
    """主程序"""
    print("===== GPU加速兼容性修复工具 =====")
    
    # 下载和配置FFmpeg
    ffmpeg_dir = Path("ffmpeg_compat")
    ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
    
    if not ffmpeg_exe.exists():
        # 下载FFmpeg
        zip_path = download_ffmpeg(FFMPEG_URL, ffmpeg_dir)
        
        # 解压FFmpeg
        ffmpeg_path = extract_ffmpeg(zip_path, ffmpeg_dir)
        
        # 删除ZIP文件
        if zip_path.exists():
            os.remove(zip_path)
            print(f"已删除zip文件: {zip_path}")
    else:
        ffmpeg_path = str(ffmpeg_exe)
        print(f"使用已存在的FFmpeg: {ffmpeg_path}")
    
    # 测试FFmpeg
    if not test_ffmpeg(ffmpeg_path):
        print("FFmpeg测试失败，修复中止!")
        return
    
    # 配置FFmpeg路径
    if not configure_ffmpeg_path(ffmpeg_path):
        print("配置FFmpeg路径失败，修复中止!")
        return
    
    # 配置GPU
    if not configure_gpu():
        print("配置GPU失败，修复中止!")
        return
    
    # 测试GPU编码
    if test_gpu_encoding(ffmpeg_path):
        print("\n===== 修复完成! =====")
        print("GPU加速已成功配置并且可以正常工作!")
        print("\n您现在可以通过主程序使用GPU加速功能来提高视频处理性能。")
    else:
        print("\n===== 修复未完成 =====")
        print("尽管我们已经配置了FFmpeg和GPU设置，但GPU编码测试失败。")
        print("建议尝试更新NVIDIA驱动后再次尝试。")

if __name__ == "__main__":
    main() 