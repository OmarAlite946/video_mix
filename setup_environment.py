#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频混剪工具 - 环境自动安装工具
用于自动安装视频混剪工具所需的所有依赖
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("environment_setup.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("SetupTool")

def print_header(title):
    """打印带格式的标题"""
    divider = "=" * 70
    print(f"\n{divider}")
    print(f"{title}".center(70))
    print(f"{divider}")
    logger.info(f"===== {title} =====")

def run_command(command, shell=False):
    """运行命令并返回结果"""
    logger.info(f"执行命令: {command}")
    try:
        if shell:
            process = subprocess.run(command, shell=True, check=True, 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
        else:
            process = subprocess.run(command, check=True, 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"命令执行失败: {e}")
        logger.error(f"错误输出: {e.stderr}")
        return False, e.stderr
    except Exception as e:
        logger.error(f"命令执行错误: {e}")
        return False, str(e)

def check_python():
    """检查Python环境"""
    print_header("检查Python环境")
    
    python_version = platform.python_version()
    logger.info(f"Python版本: {python_version}")
    print(f"Python版本: {python_version}")
    
    if not (3, 10, 0) <= sys.version_info < (3, 11, 0):
        logger.warning(f"警告: 推荐使用Python 3.10.x版本，当前版本为{python_version}")
        print(f"警告: 推荐使用Python 3.10.x版本，当前版本为{python_version}")
        
        if sys.version_info >= (3, 11, 0):
            print("当前Python版本过高，可能会导致兼容性问题")
            yn = input("是否继续安装? (y/n): ").strip().lower()
            if yn != 'y':
                sys.exit(1)
        elif sys.version_info < (3, 9, 0):
            print("当前Python版本过低，可能会导致功能缺失")
            yn = input("是否继续安装? (y/n): ").strip().lower()
            if yn != 'y':
                sys.exit(1)
    
    # 检查pip是否可用
    success, output = run_command([sys.executable, "-m", "pip", "--version"])
    if success:
        print(f"pip可用: {output.strip()}")
    else:
        print("错误: pip不可用，请确保pip已安装")
        logger.error("pip不可用")
        sys.exit(1)
    
    # 升级pip
    print("正在升级pip...")
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

def check_ffmpeg():
    """检查FFmpeg是否可用"""
    print_header("检查FFmpeg")
    
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        logger.info(f"找到FFmpeg: {ffmpeg_path}")
        print(f"找到FFmpeg: {ffmpeg_path}")
        
        success, output = run_command(["ffmpeg", "-version"])
        if success:
            version_line = output.split('\n')[0]
            logger.info(f"FFmpeg版本: {version_line}")
            print(f"FFmpeg版本: {version_line}")
        else:
            logger.warning("FFmpeg版本检查失败")
            print("警告: FFmpeg版本检查失败")
    else:
        logger.warning("未找到FFmpeg")
        print("警告: 未找到FFmpeg，视频处理功能将不可用")
        
        if platform.system() == "Windows":
            print("\n在Windows上安装FFmpeg的步骤:")
            print("1. 下载FFmpeg: https://ffmpeg.org/download.html")
            print("2. 解压到C:\\ffmpeg")
            print("3. 将C:\\ffmpeg\\bin添加到系统PATH环境变量")
            
        elif platform.system() == "Darwin":  # macOS
            print("\n在macOS上安装FFmpeg:")
            print("使用Homebrew安装: brew install ffmpeg")
            
        elif platform.system() == "Linux":
            print("\n在Linux上安装FFmpeg:")
            print("Ubuntu/Debian: sudo apt install ffmpeg")
            print("Fedora: sudo dnf install ffmpeg")
            print("Arch: sudo pacman -S ffmpeg")
        
        yn = input("是否继续安装其他依赖? (y/n): ").strip().lower()
        if yn != 'y':
            sys.exit(1)

def create_venv():
    """创建并激活虚拟环境"""
    print_header("创建虚拟环境")
    
    venv_dir = Path("venv")
    
    if venv_dir.exists():
        logger.info("虚拟环境已存在")
        print("虚拟环境已存在")
        yn = input("是否重新创建虚拟环境? (y/n): ").strip().lower()
        if yn == 'y':
            logger.info("删除现有虚拟环境")
            shutil.rmtree(venv_dir)
        else:
            return
    
    logger.info("正在创建虚拟环境...")
    print("正在创建虚拟环境，这可能需要几分钟...")
    
    success, output = run_command([sys.executable, "-m", "venv", "venv"])
    if success:
        logger.info("虚拟环境创建成功")
        print("虚拟环境创建成功")
    else:
        logger.error("虚拟环境创建失败")
        print("错误: 虚拟环境创建失败")
        yn = input("是否继续安装? (y/n): ").strip().lower()
        if yn != 'y':
            sys.exit(1)
    
    # 输出激活指令
    if platform.system() == "Windows":
        activate_cmd = "venv\\Scripts\\activate"
    else:
        activate_cmd = "source venv/bin/activate"
    
    print(f"\n要激活虚拟环境，请运行: {activate_cmd}")
    logger.info(f"激活命令: {activate_cmd}")

def install_requirements():
    """安装依赖库"""
    print_header("安装依赖库")
    
    req_file = Path("requirements.txt")
    if not req_file.exists():
        logger.error("requirements.txt文件不存在")
        print("错误: requirements.txt文件不存在")
        return False
    
    logger.info("开始安装依赖...")
    print("正在安装依赖，这可能需要几分钟...")
    
    # 根据平台确定pip命令
    if platform.system() == "Windows":
        pip_cmd = [str(Path("venv") / "Scripts" / "pip")]
    else:
        pip_cmd = [str(Path("venv") / "bin" / "pip")]
    
    # 如果虚拟环境不存在，使用系统pip
    if not Path(pip_cmd[0]).exists():
        logger.warning("虚拟环境未激活，使用系统pip")
        print("警告: 虚拟环境未激活，使用系统pip")
        pip_cmd = [sys.executable, "-m", "pip"]
    
    # 安装依赖
    success, output = run_command(pip_cmd + ["install", "-r", "requirements.txt"])
    
    if success:
        logger.info("依赖安装成功")
        print("依赖安装成功")
        return True
    else:
        logger.error("依赖安装失败")
        print("错误: 依赖安装失败，请查看日志文件获取详细信息")
        return False

def setup_pytorch_cuda():
    """安装PyTorch和CUDA支持"""
    print_header("配置PyTorch和CUDA")
    
    try:
        import torch
        logger.info(f"PyTorch已安装: {torch.__version__}")
        print(f"PyTorch已安装: {torch.__version__}")
        
        if torch.cuda.is_available():
            logger.info("CUDA可用")
            print("CUDA可用")
            return True
        else:
            logger.warning("CUDA不可用，将尝试重新安装支持CUDA的PyTorch")
            print("警告: CUDA不可用，将尝试重新安装支持CUDA的PyTorch")
    except ImportError:
        logger.info("PyTorch未安装，将安装支持CUDA的PyTorch")
        print("PyTorch未安装，将安装支持CUDA的PyTorch")
    
    # 根据平台确定pip命令
    if platform.system() == "Windows":
        pip_cmd = [str(Path("venv") / "Scripts" / "pip")]
    else:
        pip_cmd = [str(Path("venv") / "bin" / "pip")]
    
    # 如果虚拟环境不存在，使用系统pip
    if not Path(pip_cmd[0]).exists():
        pip_cmd = [sys.executable, "-m", "pip"]
    
    # 安装PyTorch (CUDA 11.8)
    print("正在安装PyTorch (CUDA 11.8)...")
    pytorch_cmd = "torch==2.0.1+cu118 torchvision==0.15.2+cu118 --index-url https://download.pytorch.org/whl/cu118"
    success, output = run_command(pip_cmd + ["install"] + pytorch_cmd.split())
    
    if success:
        logger.info("PyTorch安装成功")
        print("PyTorch安装成功")
        return True
    else:
        logger.error("PyTorch安装失败")
        print("错误: PyTorch安装失败，软件将使用CPU模式")
        return False

def check_system_compatibility():
    """检查系统兼容性"""
    print_header("系统兼容性检查")
    
    # 检查操作系统
    system = platform.system()
    logger.info(f"操作系统: {system}")
    print(f"操作系统: {system}")
    
    if system == "Windows":
        win_version = platform.win32_ver()
        logger.info(f"Windows版本: {win_version}")
        print(f"Windows版本: {win_version}")
        
        if platform.release() in ["7", "8", "8.1"]:
            logger.warning("警告: Windows 7/8/8.1可能会遇到兼容性问题")
            print("警告: Windows 7/8/8.1可能会遇到兼容性问题")
    
    # 检查硬件
    try:
        import psutil
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count(logical=True)
        memory = round(psutil.virtual_memory().total / (1024.0 ** 3), 2)  # GB
        
        logger.info(f"CPU: {cpu_cores}核心/{cpu_threads}线程")
        logger.info(f"内存: {memory} GB")
        
        print(f"CPU: {cpu_cores}核心/{cpu_threads}线程")
        print(f"内存: {memory} GB")
        
        if cpu_cores < 4:
            logger.warning("警告: CPU核心数较少，性能可能受限")
            print("警告: CPU核心数较少，性能可能受限")
        
        if memory < 8:
            logger.warning("警告: 内存较小，性能可能受限")
            print("警告: 内存较小，性能可能受限")
    
    except ImportError:
        logger.warning("psutil未安装，无法检查硬件信息")
        print("警告: psutil未安装，无法检查硬件信息")
    
    # 检查GPU (NVIDIA)
    try:
        gpu_info = ""
        if system == "Windows":
            success, output = run_command("nvidia-smi", shell=True)
            if success:
                gpu_info = output
        else:
            success, output = run_command(["nvidia-smi"])
            if success:
                gpu_info = output
        
        if gpu_info:
            logger.info("NVIDIA GPU检测到")
            print("NVIDIA GPU检测到")
            
            # 提取GPU型号和显存信息
            gpu_lines = gpu_info.split('\n')
            for i, line in enumerate(gpu_lines):
                if "NVIDIA" in line and "%" in line:
                    logger.info(f"GPU信息: {line.strip()}")
                    print(f"GPU信息: {line.strip()}")
        else:
            logger.warning("未检测到NVIDIA GPU或nvidia-smi命令不可用")
            print("警告: 未检测到NVIDIA GPU或nvidia-smi命令不可用，将使用CPU模式")
    
    except Exception as e:
        logger.warning(f"GPU检查失败: {e}")
        print("警告: GPU检查失败，将使用CPU模式")

def main():
    """主函数"""
    print("\n" + "="*70)
    print("视频混剪工具 - 环境自动安装工具".center(70))
    print("="*70)
    logger.info("开始安装流程")
    
    # 检查系统兼容性
    check_system_compatibility()
    
    # 检查Python环境
    check_python()
    
    # 检查FFmpeg
    check_ffmpeg()
    
    # 创建虚拟环境
    create_venv()
    
    # 安装依赖库
    install_requirements()
    
    # 安装PyTorch和CUDA支持
    setup_pytorch_cuda()
    
    # 安装完成
    print_header("安装完成")
    print("环境安装和配置已完成！")
    print("\n建议运行 verify_env.py 脚本检查环境是否正确配置")
    print("在Windows上，使用以下命令运行检查脚本:")
    print("venv\\Scripts\\python verify_env.py")
    
    logger.info("安装流程完成")
    print("\n" + "="*70)
    print("安装完成".center(70))
    print("="*70)
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main() 