#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
短视频批量混剪工具 - 主程序入口
"""

import sys
import os
import json
import traceback
import argparse
from pathlib import Path

# 确保可以导入src目录下的模块
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

def configure_ffmpeg():
    """配置FFmpeg路径"""
    print("=== FFmpeg配置工具 ===")
    print("此工具帮助您设置FFmpeg路径，无需管理员权限")
    print()
    
    # 获取FFmpeg路径
    ffmpeg_path = input("请输入您的FFmpeg可执行文件完整路径 (例如: C:\\FFmpeg\\bin\\ffmpeg.exe): ")
    ffmpeg_path = ffmpeg_path.strip()
    
    if not ffmpeg_path:
        print("错误: 路径不能为空！")
        return False
    
    # 检查路径是否存在
    if not os.path.exists(ffmpeg_path):
        print(f"警告: 路径不存在 - {ffmpeg_path}")
        confirm = input("是否仍然保存此路径? (y/n): ")
        if confirm.lower() != 'y':
            print("已取消设置")
            return False
    
    # 保存路径到配置文件
    try:
        with open("ffmpeg_path.txt", "w") as f:
            f.write(ffmpeg_path)
        print("FFmpeg路径已成功保存！")
        print(f"保存位置: {os.path.abspath('ffmpeg_path.txt')}")
        print("\n现在您可以不需要管理员权限也能使用软件的视频合成功能了！")
        return True
    except Exception as e:
        print(f"保存路径时出错: {str(e)}")
        return False

def display_gpu_info():
    """显示GPU详细信息"""
    try:
        from hardware.system_analyzer import SystemAnalyzer
        
        print("=== GPU详细信息检测 ===")
        print("正在检测系统GPU信息...")
        
        analyzer = SystemAnalyzer()
        system_info = analyzer.analyze()
        gpu_info = system_info.get('gpu', {})
        
        if not gpu_info.get('available', False):
            print("\n未检测到可用的GPU设备")
            return False
        
        print("\n== 基本GPU信息 ==")
        print(f"检测到GPU: {gpu_info.get('count', 0)}个")
        
        # 显示所有GPU信息
        for i, gpu in enumerate(gpu_info.get('gpus', [])):
            print(f"\nGPU {i+1}: {gpu.get('name', '未知')}")
            print(f"  厂商: {gpu.get('vendor', '未知')}")
            print(f"  类型: {gpu.get('type', '未知')}")
            
            if 'memory_total_mb' in gpu:
                print(f"  显存: {gpu.get('memory_total_mb', 0):.0f} MB")
            
            if 'driver_version' in gpu:
                print(f"  驱动版本: {gpu.get('driver_version', '未知')}")
            
            # 显示GPU能力
            capabilities = gpu.get('capabilities', {})
            if capabilities:
                print("  硬件能力:")
                print(f"    硬件编码: {'支持' if capabilities.get('hardware_encoding', False) else '不支持'}")
                print(f"    硬件解码: {'支持' if capabilities.get('hardware_decoding', False) else '不支持'}")
                
                codecs = capabilities.get('supported_codecs', [])
                if codecs:
                    print(f"    支持编解码器: {', '.join(codecs)}")
        
        # 显示加速器信息
        print("\n== 加速器信息 ==")
        accelerators = gpu_info.get('accelerators', {})
        
        # CUDA信息
        cuda_info = accelerators.get('cuda', {})
        print("CUDA支持: " + ("是" if cuda_info.get('available', False) else "否"))
        if cuda_info.get('available', False):
            print(f"  CUDA版本: {cuda_info.get('version_string', '未知')}")
            if 'device_count' in cuda_info:
                print(f"  CUDA设备数: {cuda_info.get('device_count', 0)}")
        
        # OpenCL信息
        opencl_info = accelerators.get('opencl', {})
        print("OpenCL支持: " + ("是" if opencl_info.get('available', False) else "否"))
        if opencl_info.get('available', False) and 'platforms' in opencl_info:
            for i, platform in enumerate(opencl_info.get('platforms', [])):
                print(f"  平台 {i+1}: {platform.get('name', '未知')} ({platform.get('vendor', '未知')})")
                print(f"    版本: {platform.get('version', '未知')}")
                print(f"    设备数: {len(platform.get('devices', []))}")
        
        # DirectX信息 (仅Windows)
        if 'directx' in accelerators:
            directx_info = accelerators.get('directx', {})
            print("DirectX支持: " + ("是" if directx_info.get('available', False) else "否"))
            if directx_info.get('available', False):
                print(f"  DirectX版本: {directx_info.get('version', '未知')}")
        
        # FFmpeg兼容性
        print("\n== FFmpeg硬件加速兼容性 ==")
        ffmpeg_compat = gpu_info.get('ffmpeg_compatibility', {})
        
        if 'error' in ffmpeg_compat:
            print(f"兼容性检测错误: {ffmpeg_compat.get('error', '')}")
        else:
            print("支持硬件加速: " + ("是" if ffmpeg_compat.get('hardware_acceleration', False) else "否"))
            
            encoders = ffmpeg_compat.get('recommended_encoders', [])
            if encoders:
                print(f"推荐编码器: {', '.join(encoders)}")
            
            decoders = ffmpeg_compat.get('recommended_decoders', [])
            if decoders:
                print(f"推荐解码器: {', '.join(decoders)}")
        
        # 导出JSON文件
        try:
            with open("gpu_info.json", "w", encoding="utf-8") as f:
                json.dump(gpu_info, f, ensure_ascii=False, indent=2)
            print(f"\nGPU信息已导出到: {os.path.abspath('gpu_info.json')}")
        except Exception as e:
            print(f"导出信息时出错: {str(e)}")
        
        return True
    
    except Exception as e:
        print(f"检测GPU信息时出错: {str(e)}")
        traceback.print_exc()
        return False

def handle_exception(exc_type, exc_value, exc_traceback):
    """全局异常处理"""
    if issubclass(exc_type, KeyboardInterrupt):
        # 正常退出
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # 记录未捕获的异常
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"发生未捕获的异常:\n{error_msg}")
    # 这里可以添加错误日志记录或弹窗提示

# 设置全局异常处理
sys.excepthook = handle_exception

def main():
    """程序主入口"""
    parser = argparse.ArgumentParser(description="短视频批量混剪工具")
    parser.add_argument("--config-ffmpeg", action="store_true", help="配置FFmpeg路径后退出")
    parser.add_argument("--gpu-info", action="store_true", help="显示详细GPU信息后退出")
    parser.add_argument("--reset-gpu-config", action="store_true", help="重置GPU配置后退出")
    parser.add_argument("--batch-mode", action="store_true", help="启动多模板批处理模式")
    args = parser.parse_args()
    
    # 如果指定了配置FFmpeg，则运行配置工具后退出
    if args.config_ffmpeg:
        success = configure_ffmpeg()
        return 0 if success else 1
    
    # 如果指定了显示GPU信息，则运行GPU检测工具后退出
    if args.gpu_info:
        success = display_gpu_info()
        return 0 if success else 1
    
    try:
        from PyQt5.QtWidgets import QApplication
        from src.ui.main_window import MainWindow
        from src.ui.batch_window import BatchWindow
        from src.utils.logger import setup_logger
        from src.hardware.system_analyzer import SystemAnalyzer
        from src.hardware.gpu_config import GPUConfig
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保已安装所有依赖: pip install -r requirements.txt")
        sys.exit(1)
    
    # 设置日志
    setup_logger()
    
    # 如果指定了重置GPU配置，则进行重置后退出
    if args.reset_gpu_config:
        print("正在重置GPU配置...")
        gpu_config = GPUConfig()
        gpu_config._set_cpu_config()
        print("GPU配置已重置为CPU模式")
        return 0
    
    app = QApplication(sys.argv)
    app.setApplicationName("视频混剪工具")
    app.setOrganizationName("VideoMixTool")
    
    # 检测系统硬件
    analyzer = SystemAnalyzer()
    system_info = analyzer.analyze()
    
    # 简单显示系统信息
    print("系统信息:")
    print(f"  操作系统: {system_info.get('os', '未知')} {system_info.get('os_version', '未知')}")
    print(f"  CPU: {system_info.get('cpu', {}).get('model', '未知')}")
    print(f"  内存: {system_info.get('memory', {}).get('total_gb', 0):.1f} GB")
    
    # 显示GPU信息
    gpu_info = system_info.get('gpu', {})
    if gpu_info.get('available', False):
        primary_gpu = gpu_info.get('primary_gpu', '未知')
        primary_vendor = gpu_info.get('primary_vendor', '未知')
        print(f"  GPU: {primary_gpu} ({primary_vendor})")
        
        # 显示硬件加速信息
        ffmpeg_compat = gpu_info.get('ffmpeg_compatibility', {})
        if ffmpeg_compat.get('hardware_acceleration', False):
            encoders = ffmpeg_compat.get('recommended_encoders', [])
            if encoders:
                print(f"  可用硬件加速编码器: {', '.join(encoders)}")
        
        print("\n若要查看完整GPU信息，请使用参数：--gpu-info")
    else:
        print("  未检测到可用的GPU")
    
    # 初始化GPU配置
    gpu_config = GPUConfig()
    if gpu_config.is_hardware_acceleration_enabled():
        gpu_name, gpu_vendor = gpu_config.get_gpu_info()
        encoder = gpu_config.get_encoder()
        print(f"\n已启用GPU硬件加速:")
        print(f"  硬件: {gpu_name} ({gpu_vendor})")
        print(f"  编码器: {encoder}")
    else:
        print("\n当前使用CPU编码 (libx264)")
    
    # 决定使用哪个窗口
    if args.batch_mode:
        # 批处理模式：启动多模板批处理窗口
        window = BatchWindow()
        print("\n已启动多模板批处理模式")
    else:
        # 标准模式：启动单一模板窗口
        window = MainWindow()
        print("\n已启动标准模式")
    
    window.show()
    
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 