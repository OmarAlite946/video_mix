#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU编码测试脚本
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# 添加src目录到路径
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

from hardware.gpu_config import GPUConfig, CONFIG_FILE
from hardware.system_analyzer import SystemAnalyzer

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ffmpeg_gpu():
    """测试FFmpeg GPU编码功能"""
    print("正在测试FFmpeg GPU编码能力...")
    
    # 创建临时目录
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    # 创建一个测试视频文件（如果不存在）
    test_input = temp_dir / "test_input.mp4"
    if not test_input.exists():
        print("正在生成测试视频...")
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", 
            "testsrc=duration=5:size=1280x720:rate=30", 
            "-c:v", "libx264", "-crf", "23", str(test_input)
        ]
        subprocess.run(cmd, check=True)
    
    # 测试GPU编码
    test_output = temp_dir / "test_output_gpu.mp4"
    nvenc_cmd = [
        "ffmpeg", "-y", "-i", str(test_input),
        "-c:v", "h264_nvenc", 
        "-preset", "p2",
        "-tune", "hq",
        "-b:v", "5000k",
        str(test_output)
    ]
    
    print("\n正在使用NVENC编码器测试...")
    print(f"命令: {' '.join(nvenc_cmd)}")
    
    # 记录开始时间
    start_time = time.time()
    
    # 执行命令
    try:
        process = subprocess.Popen(
            nvenc_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            text=True
        )
        
        # 显示输出
        for line in process.stdout:
            print(line.strip())
        
        # 等待进程完成
        process.wait()
        
        # 计算处理时间
        encode_time = time.time() - start_time
        
        if process.returncode == 0:
            print(f"\nNVENC编码成功! 用时: {encode_time:.2f}秒")
            print(f"输出文件: {test_output}")
            
            # 显示输出文件信息
            if test_output.exists():
                file_size = os.path.getsize(test_output) / (1024 * 1024)  # MB
                print(f"输出文件大小: {file_size:.2f} MB")
                
                # 验证文件是否使用了NVENC编码
                info_cmd = ["ffmpeg", "-i", str(test_output)]
                info_process = subprocess.Popen(
                    info_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                _, stderr = info_process.communicate()
                print("\n文件信息:")
                print(stderr)
                
                return True
        else:
            print(f"\nNVENC编码失败，返回码: {process.returncode}")
            return False
            
    except Exception as e:
        print(f"测试过程中出错: {e}")
        return False

def force_enable_gpu():
    """强制启用GPU配置"""
    print("正在强制启用GPU配置...")
    
    # 检测GPU
    analyzer = SystemAnalyzer()
    system_info = analyzer.analyze()
    gpu_info = system_info.get('gpu', {})
    
    # 显示GPU信息
    if gpu_info.get('available', False):
        print(f"检测到GPU: {gpu_info.get('primary_gpu', '未知')} ({gpu_info.get('primary_vendor', '未知')})")
        
        # 强制设置GPU配置
        gpu_config = GPUConfig()
        gpu_config.config['use_hardware_acceleration'] = True
        gpu_config.config['encoder'] = 'h264_nvenc'
        gpu_config.config['decoder'] = 'h264_cuvid'
        gpu_config.config['encoding_preset'] = 'p2'
        gpu_config.config['detected_gpu'] = gpu_info.get('primary_gpu', 'NVIDIA GPU')
        gpu_config.config['detected_vendor'] = gpu_info.get('primary_vendor', 'NVIDIA')
        gpu_config.config['extra_params'] = {
            'spatial-aq': '1',
            'temporal-aq': '1'
        }
        
        # 保存配置
        gpu_config._save_config()
        
        print("GPU配置已强制启用!")
        print(f"配置文件保存在: {CONFIG_FILE}")
        return True
    else:
        print("未检测到可用的GPU!")
        return False

if __name__ == "__main__":
    print("===== GPU加速测试工具 =====")
    
    # 强制启用GPU
    force_enable_gpu()
    
    # 测试FFmpeg GPU编码
    test_ffmpeg_gpu() 