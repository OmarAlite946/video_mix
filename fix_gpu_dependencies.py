#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU依赖修复工具
用于修复GPU检测所需的所有依赖
"""

import os
import sys
import subprocess
import platform
import time
import logging
from pathlib import Path

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   encoding='utf-8')
logger = logging.getLogger(__name__)

def check_pip():
    """检查pip是否可用"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                       check=True, capture_output=True, text=True)
        return True
    except Exception as e:
        logger.error(f"检查pip时出错: {e}")
        return False

def install_package(package_name):
    """安装Python包"""
    logger.info(f"正在安装 {package_name}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
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

def install_gpu_dependencies():
    """安装GPU检测相关依赖"""
    
    # 基础依赖
    basic_deps = [
        "numpy==1.24.3",
        "psutil==5.9.5",
        "GPUtil==1.4.0",
        "Pillow==10.0.1",
        "scipy==1.11.3",
        "setuptools==69.0.3",
        "wheel==0.42.0",
        "siphash24==0.5.0"  # 解决 RecommendedHashNotFoundWarning
    ]
    
    # NVIDIA GPU依赖
    nvidia_deps = [
        "pycuda==2022.2.2"
    ]
    
    # OpenCL依赖
    opencl_deps = [
        "pyopencl==2023.1.4"
    ]
    
    # 安装基础依赖
    logger.info("正在安装基础依赖...")
    for dep in basic_deps:
        install_package(dep)
    
    # 安装NVIDIA GPU依赖
    logger.info("正在安装NVIDIA GPU依赖...")
    for dep in nvidia_deps:
        # pycuda安装可能会失败，但不阻止程序继续
        try:
            install_package(dep)
        except Exception as e:
            logger.warning(f"安装 {dep} 时出现警告: {e}")
    
    # 安装OpenCL依赖
    logger.info("正在安装OpenCL依赖...")
    for dep in opencl_deps:
        # pyopencl安装可能会失败，但不阻止程序继续
        try:
            install_package(dep)
        except Exception as e:
            logger.warning(f"安装 {dep} 时出现警告: {e}")
    
    logger.info("所有依赖安装完成!")

def fix_gpu_config():
    """修复GPU配置"""
    logger.info("正在修复GPU配置...")
    
    # 添加src目录到路径
    src_dir = Path(__file__).resolve().parent / 'src'
    sys.path.insert(0, str(src_dir))
    
    try:
        # 清除旧的GPU配置
        config_dir = Path.home() / "VideoMixTool"
        config_file = config_dir / "gpu_config.json"
        
        if config_file.exists():
            logger.info(f"正在删除旧的GPU配置: {config_file}")
            config_file.unlink()
            logger.info("旧配置已删除")
        
        # 创建NVIDIA GPU配置
        logger.info("正在创建新的GPU配置...")
        
        # 检查NVIDIA GPU是否可用
        try:
            logger.info("正在检查NVIDIA驱动...")
            
            # 使用nvidia-smi检查NVIDIA GPU
            result = subprocess.run(
                ["nvidia-smi"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            
            if result.returncode == 0 and "NVIDIA-SMI" in result.stdout:
                logger.info("NVIDIA GPU可用，正在创建配置...")
                
                # 创建配置目录
                config_dir.mkdir(exist_ok=True, parents=True)
                
                # 创建新的配置
                import json
                gpu_config = {
                    "use_hardware_acceleration": True,
                    "encoder": "h264_nvenc",
                    "decoder": "h264_cuvid",
                    "encoding_preset": "p2",
                    "extra_params": {
                        "spatial-aq": "1",
                        "temporal-aq": "1"
                    },
                    "detected_gpu": "NVIDIA GPU",
                    "detected_vendor": "NVIDIA",
                    "compatibility_mode": True,
                    "driver_version": "Unknown"
                }
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(gpu_config, f, ensure_ascii=False, indent=2)
                
                logger.info(f"GPU配置已创建: {config_file}")
                
                return True
            else:
                logger.warning("NVIDIA GPU不可用或未安装驱动")
                return False
        except Exception as e:
            logger.error(f"检查NVIDIA GPU时出错: {e}")
            return False
        
    except Exception as e:
        logger.error(f"修复GPU配置时出错: {e}")
        return False

def patch_gpu_detection():
    """修补GPU检测相关代码"""
    logger.info("正在修补GPU检测代码...")
    
    # 修补system_analyzer.py
    system_analyzer_path = Path(__file__).resolve().parent / 'src' / 'hardware' / 'system_analyzer.py'
    
    if not system_analyzer_path.exists():
        logger.error(f"未找到文件: {system_analyzer_path}")
        return False
    
    try:
        # 读取原始文件
        with open(system_analyzer_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 修改内容 - 增强NVIDIA GPU检测
        if '_check_nvidia_gpu_available' not in content:
            # 在合适的位置添加增强的NVIDIA检测方法
            new_method = """
    def _check_nvidia_gpu_available(self):
        \"\"\"检查系统是否有可用的NVIDIA GPU\"\"\"
        try:
            # 尝试多种方法检测NVIDIA GPU
            
            # 方法1: 使用nvidia-smi命令
            import subprocess
            try:
                result = subprocess.run(
                    ["nvidia-smi"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    shell=True,
                    timeout=3
                )
                if result.returncode == 0:
                    output = result.stdout.decode('utf-8', errors='ignore')
                    if 'NVIDIA-SMI' in output and 'Driver Version' in output:
                        # 提取GPU名称
                        import re
                        gpu_name = "NVIDIA GPU"
                        gpu_match = re.search(r'\\| {1,2}([A-Za-z]+ [A-Za-z]+ [A-Za-z0-9]+)', output)
                        if gpu_match:
                            gpu_name = gpu_match.group(1).strip()
                        return True
            except Exception:
                pass
            
            # 方法2: 使用PyNVML检测
            try:
                import pynvml
                pynvml.nvmlInit()
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    return True
            except Exception:
                pass
            
            # 方法3: 使用GPUtil
            if HAS_GPUTIL:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        return True
                except Exception:
                    pass
            
            # 方法4: 使用PyCUDA
            if HAS_PYCUDA:
                try:
                    cuda.init()
                    device_count = cuda.Device.count()
                    if device_count > 0:
                        return True
                except Exception:
                    pass
            
            return False
        except Exception as e:
            print(f"检测NVIDIA GPU时出错: {e}")
            return False
"""
            
            # 在_analyze_gpu_basic方法之后插入新方法
            content = content.replace("    def _analyze_gpu_deep(self):", new_method + "\n    def _analyze_gpu_deep(self):")
        
        # 增强远程显示适配
        if "remote_display_detected = False" in content and "虚拟显示卡" not in content:
            # 替换远程显示检测逻辑
            improved_detection = """        # 标记是否检测到了远程显示驱动
        remote_display_detected = False
        
        # 即使检测到远程显示，也尝试检测物理GPU
        has_physical_gpu = self._check_nvidia_gpu_available()
        if has_physical_gpu:
            gpu_info['available'] = True
            # 添加NVIDIA GPU信息
            gpu = {
                'index': 0,
                'name': 'NVIDIA GPU',
                'vendor': 'NVIDIA',
                'type': 'dedicated',
                'memory_total_mb': 4096,  # 默认4GB显存
                'driver_version': 'Unknown'
            }
            gpu_info['gpus'].append(gpu)
            gpu_info['primary_gpu'] = 'NVIDIA GPU'
            gpu_info['primary_vendor'] = 'NVIDIA'
            
            # 设置FFmpeg兼容性
            gpu_info['ffmpeg_compatibility'] = {
                'hardware_acceleration': True,
                'recommended_encoders': ['h264_nvenc'],
                'recommended_decoders': ['h264_cuvid']
            }
            
            return gpu_info
"""
            
            content = content.replace("        # 标记是否检测到了远程显示驱动\n        remote_display_detected = False", improved_detection)
        
        # 写回修改后的文件
        with open(system_analyzer_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("GPU检测代码修补完成!")
        return True
        
    except Exception as e:
        logger.error(f"修补GPU检测代码时出错: {e}")
        return False

def main():
    """主程序"""
    print("===== GPU依赖修复工具 =====")
    print("此工具将修复GPU检测所需的所有依赖")
    print()
    
    # 检查pip
    if not check_pip():
        print("错误: pip不可用，请确保您的Python环境正确配置")
        return
    
    # 安装依赖
    print("步骤1: 安装依赖")
    install_gpu_dependencies()
    print()
    
    # 修复GPU配置
    print("步骤2: 修复GPU配置")
    fix_gpu_config()
    print()
    
    # 修补GPU检测代码
    print("步骤3: 修补GPU检测代码")
    patch_gpu_detection()
    print()
    
    print("修复完成! 请重启应用程序测试GPU检测")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"执行修复工具时出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 等待用户按键退出
    input("按回车键退出...") 