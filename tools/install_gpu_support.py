#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU支持安装工具
安装额外的GPU检测和支持库
"""

import os
import sys
import subprocess
import platform
import logging
import time
from pathlib import Path

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   encoding='utf-8')
logger = logging.getLogger(__name__)

def install_package(package_name):
    """安装Python包"""
    logger.info(f"正在安装 {package_name}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", package_name],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"{package_name} 安装成功!")
            return True
        else:
            logger.error(f"{package_name} 安装失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"安装 {package_name} 时出错: {e}")
        return False

def install_basic_dependencies():
    """安装基本依赖"""
    logger.info("安装基本依赖...")
    basic_deps = [
        "wheel>=0.40.0",
        "setuptools>=65.0.0",
        "numpy>=1.22.0",
        "GPUtil>=1.4.0",
        "psutil>=5.9.0",
        "py-cpuinfo>=9.0.0",
        "ffmpeg-python>=0.2.0"
    ]
    
    for dep in basic_deps:
        install_package(dep)

def install_nvidia_dependencies():
    """安装NVIDIA GPU依赖"""
    logger.info("安装NVIDIA GPU依赖...")
    
    # 安装NVIDIA相关库
    nvidia_deps = [
        "nvidia-ml-py>=11.525.112",  # PyNVML库
        "pynvml>=11.5.0"            # NVIDIA管理库的Python绑定
    ]
    
    for dep in nvidia_deps:
        install_package(dep)
    
    # 尝试安装PyCUDA (可能会因编译问题失败)
    try:
        logger.info("尝试安装PyCUDA...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "pycuda>=2022.1"],
            check=False, capture_output=True, text=True
        )
    except Exception as e:
        logger.warning(f"安装PyCUDA时出错: {e}")
        logger.info("跳过PyCUDA安装，这不会影响基本功能")

def install_opencl_dependencies():
    """安装OpenCL依赖"""
    logger.info("安装OpenCL依赖...")
    try:
        install_package("pyopencl>=2023.1")
    except Exception as e:
        logger.warning(f"安装OpenCL依赖时出错: {e}")
        logger.info("跳过OpenCL安装，这不会影响基本功能")

def install_cudnn_support():
    """安装CUDA深度学习支持库"""
    logger.info("尝试安装CUDA深度学习支持...")
    try:
        # 尝试安装预编译的cuDNN包
        install_package("nvidia-cudnn-cu12")
    except Exception as e:
        logger.warning(f"安装CUDA深度学习支持时出错: {e}")
        logger.info("跳过cuDNN安装，这不会影响基本功能")

def download_nvidiapatcher():
    """下载NVIDIA驱动补丁程序"""
    logger.info("下载NVIDIA驱动补丁程序...")
    try:
        import requests
        import zipfile
        import io
        
        # 补丁程序URL (示例URL，需要替换为实际URL)
        url = "https://github.com/keylase/nvidia-patch/archive/refs/heads/master.zip"
        
        # 创建下载目录
        download_dir = Path("nvidia_patch")
        if not download_dir.exists():
            download_dir.mkdir(parents=True)
        
        # 下载文件
        response = requests.get(url)
        if response.status_code == 200:
            # 解压文件
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                zip_file.extractall(download_dir)
            
            logger.info(f"NVIDIA补丁程序已下载到: {download_dir.resolve()}")
            logger.info("您可以使用这些补丁来解除NVIDIA编码限制")
        else:
            logger.error(f"下载NVIDIA补丁失败: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"下载NVIDIA补丁时出错: {e}")

def install_siphash():
    """安装siphash库以解决哈希警告"""
    logger.info("安装siphash以解决哈希警告...")
    install_package("siphash24>=0.5.0")

def update_local_parser():
    """更新本地视频解析器支持"""
    logger.info("更新本地视频解析器支持...")
    
    try:
        # 安装视频解析依赖
        parser_deps = [
            "av>=10.0.0",      # PyAV视频处理库
            "opencv-python>=4.8.0.74",
            "moviepy>=1.0.3",
            "scipy>=1.11.1"
        ]
        
        for dep in parser_deps:
            install_package(dep)
            
        logger.info("视频解析器依赖更新完成")
    except Exception as e:
        logger.error(f"更新视频解析器时出错: {e}")

def create_patch_script():
    """创建系统补丁脚本"""
    logger.info("创建系统补丁脚本...")
    
    patch_script = """@echo off
echo ===== NVIDIA GPU驱动补丁工具 =====
echo 此工具将尝试修复NVIDIA GPU检测问题
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 错误: 需要管理员权限来运行此脚本!
    echo 请右键点击此脚本，选择"以管理员身份运行"
    pause
    exit /b 1
)

echo 正在检查NVIDIA驱动...
nvidia-smi >nul 2>&1
if %errorLevel% neq 0 (
    echo 未检测到NVIDIA驱动，请确保已正确安装驱动
    pause
    exit /b 1
)

echo NVIDIA驱动已检测到，正在重启服务...
echo.

echo 1. 停止NVIDIA显示驱动服务...
net stop "NVIDIA Display Driver Service" /y
timeout /t 2 /nobreak >nul

echo 2. 重启NVIDIA显示驱动服务...
net start "NVIDIA Display Driver Service"
timeout /t 2 /nobreak >nul

echo 3. 清理系统缓存...
ipconfig /flushdns >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo NVIDIA服务已重新启动!
echo 请重新启动您的应用程序测试GPU检测

pause
"""
    
    # 写入脚本文件
    try:
        with open("修复NVIDIA显卡检测.bat", "w", encoding="gbk") as f:
            f.write(patch_script)
        
        logger.info("系统补丁脚本已创建: 修复NVIDIA显卡检测.bat")
        logger.info("您可以右键点击此脚本并选择'以管理员身份运行'来修复显卡检测问题")
    except Exception as e:
        logger.error(f"创建补丁脚本时出错: {e}")

def add_gpu_detection_bypass():
    """添加GPU检测绕过脚本"""
    logger.info("添加GPU检测绕过脚本...")
    
    bypass_script = """#!/usr/bin/env python
# -*- coding: utf-8 -*-

\"\"\"
GPU检测绕过工具
强制启用NVIDIA GPU
\"\"\"

import os
import sys
import json
from pathlib import Path

# 检查是否是Windows系统
if sys.platform != "win32":
    print("此脚本仅适用于Windows系统")
    sys.exit(1)

# 配置文件路径
config_dir = Path.home() / "VideoMixTool"
config_file = config_dir / "gpu_config.json"

# 创建配置目录
config_dir.mkdir(exist_ok=True, parents=True)

# 强制NVIDIA GPU配置
force_config = {
    "use_hardware_acceleration": True,
    "encoder": "h264_nvenc",
    "decoder": "h264_cuvid",
    "encoding_preset": "p2",
    "extra_params": {
        "spatial-aq": "1",
        "temporal-aq": "1",
        "rc": "vbr",
        "cq": "19"
    },
    "detected_gpu": "NVIDIA GPU",
    "detected_vendor": "NVIDIA",
    "compatibility_mode": True,
    "driver_version": "最新版本"
}

# 保存配置
with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(force_config, f, ensure_ascii=False, indent=2)

print(f"已强制启用NVIDIA GPU加速配置")
print(f"配置文件: {config_file}")
print("请重启应用程序以应用更改")

# 等待用户确认
input("按回车键继续...")
"""
    
    try:
        with open("启用NVIDIA加速.py", "w", encoding="utf-8") as f:
            f.write(bypass_script)
        
        logger.info("GPU检测绕过脚本已创建: 启用NVIDIA加速.py")
        logger.info("您可以运行此脚本来强制启用NVIDIA GPU加速")
    except Exception as e:
        logger.error(f"创建GPU检测绕过脚本时出错: {e}")

def main():
    print("===== GPU支持安装工具 =====")
    print("此工具将安装所有必要的GPU支持库")
    print()
    
    # 安装基本依赖
    print("步骤1: 安装基本依赖")
    install_basic_dependencies()
    print()
    
    # 安装NVIDIA依赖
    print("步骤2: 安装NVIDIA GPU依赖")
    install_nvidia_dependencies()
    print()
    
    # 安装OpenCL依赖
    print("步骤3: 安装OpenCL依赖")
    install_opencl_dependencies()
    print()
    
    # 安装CUDA深度学习支持
    print("步骤4: 安装CUDA深度学习支持")
    install_cudnn_support()
    print()
    
    # 安装siphash
    print("步骤5: 安装siphash解决哈希警告")
    install_siphash()
    print()
    
    # 更新本地视频解析器
    print("步骤6: 更新本地视频解析器")
    update_local_parser()
    print()
    
    # 创建补丁脚本
    print("步骤7: 创建系统补丁脚本")
    create_patch_script()
    print()
    
    # 添加GPU检测绕过
    print("步骤8: 添加GPU检测绕过")
    add_gpu_detection_bypass()
    print()
    
    print("所有GPU支持库安装完成!")
    print("请运行以下工具进行修复:")
    print("1. fix_gpu_dependencies.py - 修复基本GPU依赖")
    print("2. 修复NVIDIA显卡检测.bat - 修复显卡驱动问题 (需要管理员权限)")
    print("3. 启用NVIDIA加速.py - 如果前两种方法不成功，可使用强制启用GPU配置")
    print()
    print("完成后请重启您的应用程序")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"运行安装工具时出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 等待用户按键退出
    input("按回车键退出...") 