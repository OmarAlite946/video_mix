#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频混剪工具环境验证脚本
用于检查当前环境是否满足运行视频混剪工具的所有必要条件
"""

import sys
import os
import subprocess
import pkg_resources
import platform
import shutil
from pathlib import Path

def print_header(title):
    """打印带格式的标题"""
    print("\n" + "="*50)
    print(f"{title}".center(50))
    print("="*50)

def print_result(name, status, details=""):
    """打印检查结果"""
    status_symbol = "✓" if status else "✗"
    print(f"{status_symbol} {name:<30} {details}")

def check_python_version():
    """检查Python版本"""
    print_header("Python环境检查")
    
    version = platform.python_version()
    is_valid = (3, 10, 0) <= sys.version_info < (3, 11, 0)
    print_result("Python版本", is_valid, f"{version} (推荐: 3.10.x)")
    
    # 检查Python路径
    python_path = sys.executable
    print_result("Python安装路径", True, python_path)
    
    # 检查pip
    try:
        pip_version = subprocess.check_output([sys.executable, "-m", "pip", "--version"], 
                                             text=True).strip()
        print_result("pip版本", True, pip_version)
    except Exception as e:
        print_result("pip", False, f"错误: {e}")

def check_ffmpeg():
    """检查FFmpeg是否安装"""
    print_header("FFmpeg检查")
    
    # 检查命令行可访问性
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print_result("FFmpeg路径", True, ffmpeg_path)
        
        # 获取版本
        try:
            result = subprocess.run(["ffmpeg", "-version"], 
                                   capture_output=True, text=True)
            version = result.stdout.split("\n")[0]
            print_result("FFmpeg版本", True, version)
        except Exception as e:
            print_result("FFmpeg版本检查", False, f"错误: {e}")
    else:
        print_result("FFmpeg", False, "未找到FFmpeg，请确保已安装并添加到PATH")
        print("\n提示: 您可以从 https://ffmpeg.org/download.html 下载FFmpeg")

def check_cuda():
    """检查CUDA和GPU支持"""
    print_header("CUDA和GPU支持检查")
    
    try:
        import torch
        print_result("PyTorch", True, f"版本: {torch.__version__}")
        
        cuda_available = torch.cuda.is_available()
        print_result("CUDA可用", cuda_available)
        
        if cuda_available:
            cuda_version = torch.version.cuda
            print_result("CUDA版本", True, cuda_version)
            
            try:
                cudnn_version = torch.backends.cudnn.version()
                print_result("cuDNN版本", True, str(cudnn_version))
            except Exception:
                print_result("cuDNN版本", False, "无法检测")
            
            device_count = torch.cuda.device_count()
            print_result("GPU数量", True, str(device_count))
            
            for i in range(device_count):
                device_name = torch.cuda.get_device_name(i)
                print_result(f"GPU {i}", True, device_name)
        else:
            print("\n注意: 未检测到CUDA支持，软件将使用CPU模式运行，性能可能受限")
            
    except ImportError:
        print_result("PyTorch", False, "未安装，GPU加速将不可用")
    except Exception as e:
        print_result("CUDA检查", False, f"错误: {e}")

def check_libraries():
    """检查关键库是否安装及其版本"""
    print_header("Python依赖库检查")
    
    requirements = {
        # GUI相关
        "PyQt5": {"required": "5.15.9", "category": "GUI"},
        "PyQt5-sip": {"required": "12.12.2", "category": "GUI"},
        
        # 视频处理
        "opencv-python": {"required": "4.8.0.76", "category": "视频处理"},
        "numpy": {"required": "1.24.3", "category": "视频处理"},
        "pillow": {"required": "10.0.0", "category": "视频处理"},
        "moviepy": {"required": "1.0.3", "category": "视频处理"},
        "scikit-image": {"required": "0.21.0", "category": "视频处理"},
        
        # 音频处理
        "pydub": {"required": "0.25.1", "category": "音频处理"},
        
        # 硬件加速
        "torch": {"required": "2.0.1", "category": "硬件加速"},
        "torchvision": {"required": "0.15.2", "category": "硬件加速"},
        
        # 工具库
        "tqdm": {"required": "4.65.0", "category": "工具"},
        "psutil": {"required": "5.9.5", "category": "工具"},
        "requests": {"required": "2.31.0", "category": "工具"},
    }
    
    categories = {}
    
    # 获取已安装的库版本
    for package, info in requirements.items():
        category = info["category"]
        required = info["required"]
        
        if category not in categories:
            categories[category] = []
        
        try:
            installed = pkg_resources.get_distribution(package).version
            status = installed == required
            categories[category].append((package, status, installed, required))
        except pkg_resources.DistributionNotFound:
            categories[category].append((package, False, "未安装", required))
        except Exception as e:
            categories[category].append((package, False, f"错误: {e}", required))
    
    # 按类别打印结果
    for category, packages in categories.items():
        print(f"\n{category}:")
        for package, status, installed, required in packages:
            print_result(package, status, f"已安装: {installed} (推荐: {required})")

def check_installation_path():
    """检查安装路径和权限"""
    print_header("环境路径和权限检查")
    
    # 检查当前工作目录
    cwd = os.getcwd()
    print_result("当前工作目录", True, cwd)
    
    # 检查是否有写入权限
    try:
        test_file = Path(cwd) / "write_test.tmp"
        with open(test_file, "w") as f:
            f.write("test")
        test_file.unlink()
        print_result("写入权限", True, "当前目录可写")
    except Exception as e:
        print_result("写入权限", False, f"错误: {e}")
    
    # 检查用户主目录
    home = Path.home()
    user_data_dir = home / "VideoMixTool"
    print_result("用户数据目录", user_data_dir.exists(), str(user_data_dir))
    
    # 检查环境变量
    path_env = os.environ.get("PATH", "").split(os.pathsep)
    python_in_path = any("python" in p.lower() for p in path_env)
    print_result("Python在PATH中", python_in_path)
    
    ffmpeg_in_path = any("ffmpeg" in p.lower() for p in path_env)
    print_result("FFmpeg在PATH中", ffmpeg_in_path)

def main():
    """主函数"""
    print("\n" + "="*70)
    print("视频混剪工具 - 环境验证工具".center(70))
    print("="*70)
    
    # 检查Python
    check_python_version()
    
    # 检查FFmpeg
    check_ffmpeg()
    
    # 检查CUDA和GPU
    check_cuda()
    
    # 检查依赖库
    check_libraries()
    
    # 检查安装路径
    check_installation_path()
    
    print("\n" + "="*70)
    print("环境检查完成".center(70))
    print("="*70 + "\n")
    
    input("按回车键退出...")

if __name__ == "__main__":
    main() 