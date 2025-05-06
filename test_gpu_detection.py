#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU检测测试工具
用于测试显卡识别功能是否正常工作
"""

import os
import sys
import time
import json
import subprocess
import platform
from pathlib import Path
import ctypes
import tempfile
import shutil

# 设置颜色输出
if platform.system() == 'Windows':
    os.system('color')
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'
else:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# 添加src目录到路径
src_dir = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(src_dir))

# 检查所需的依赖库
try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False
    print(f"{YELLOW}未安装GPUtil库，将使用备用检测方法{END}")

try:
    import pycuda.driver as cuda
    import pycuda.autoinit
    HAS_PYCUDA = True
except ImportError:
    HAS_PYCUDA = False
    print(f"{YELLOW}未安装PyCUDA库，将使用备用检测方法{END}")

try:
    import pyopencl as cl
    HAS_PYOPENCL = True
except ImportError:
    HAS_PYOPENCL = False
    print(f"{YELLOW}未安装PyOpenCL库，将使用备用检测方法{END}")

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False
    print(f"{YELLOW}未安装PyNVML库，将使用备用检测方法{END}")

# 创建临时目录
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

def format_size(size_bytes):
    """格式化文件大小为人类可读格式"""
    if size_bytes < 1024:
        return f"{size_bytes:.2f} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"

def create_test_video():
    """创建测试视频用于编码测试"""
    test_video_path = TEMP_DIR / "test_input.mp4"
    
    # 如果测试视频已存在，直接返回路径
    if test_video_path.exists():
        return test_video_path
    
    # 创建测试视频
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=1280x720:rate=30", 
        "-c:v", "libx264", "-crf", "23", str(test_video_path)
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return test_video_path
    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"{RED}无法创建测试视频，跳过编码测试{END}")
        return None

def check_nvidia_smi():
    """使用nvidia-smi命令检测NVIDIA GPU"""
    print(f"\n{BOLD}=== 使用nvidia-smi测试 ==={END}")
    
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,memory.free", "--format=csv,noheader"], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            print(f"{GREEN}检测到 {len(lines)} 个NVIDIA GPU:{END}")
            
            for i, line in enumerate(lines):
                parts = [part.strip() for part in line.split(',')]
                if len(parts) >= 5:
                    print(f"  GPU {i}: {parts[0]}")
                    print(f"    驱动版本: {parts[1]}")
                    print(f"    总显存: {parts[2]}")
                    print(f"    已用显存: {parts[3]}")
                    print(f"    可用显存: {parts[4]}")
            
            print(f"{GREEN}✓ nvidia-smi检测成功{END}")
            return True
        else:
            print(f"{RED}× nvidia-smi未返回GPU信息{END}")
            return False
    
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"{RED}× nvidia-smi调用失败: {str(e)}{END}")
        return False

def check_wmi_gpu():
    """使用WMI检测Windows GPU信息"""
    if platform.system() != 'Windows':
        print(f"{YELLOW}非Windows系统，跳过WMI测试{END}")
        return False
    
    print(f"\n{BOLD}=== 使用WMI测试 ==={END}")
    
    try:
        result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM,DriverVersion,PNPDeviceID", "/format:csv"], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            header = None
            gpu_count = 0
            
            for line in lines:
                if not line.strip():
                    continue
                
                parts = [part.strip() for part in line.split(',')]
                if not header and len(parts) >= 4:
                    header = parts
                    continue
                
                if header and len(parts) >= len(header):
                    gpu_count += 1
                    node_name_idx = header.index("Node") if "Node" in header else 0
                    name_idx = header.index("Name") if "Name" in header else 1
                    adapter_ram_idx = header.index("AdapterRAM") if "AdapterRAM" in header else 2
                    driver_version_idx = header.index("DriverVersion") if "DriverVersion" in header else 3
                    pnp_id_idx = header.index("PNPDeviceID") if "PNPDeviceID" in header else 4
                    
                    name = parts[name_idx] if name_idx < len(parts) else "Unknown"
                    ram = parts[adapter_ram_idx] if adapter_ram_idx < len(parts) else "0"
                    driver = parts[driver_version_idx] if driver_version_idx < len(parts) else "Unknown"
                    pnp_id = parts[pnp_id_idx] if pnp_id_idx < len(parts) else ""
                    
                    try:
                        ram_mb = int(ram) / (1024 * 1024)
                        ram_str = f"{ram_mb:.2f} MB"
                    except ValueError:
                        ram_str = "Unknown"
                    
                    print(f"  GPU {gpu_count-1}: {name}")
                    print(f"    显存: {ram_str}")
                    print(f"    驱动版本: {driver}")
                    if "nvidia" in pnp_id.lower():
                        print(f"    类型: NVIDIA GPU")
            
            if gpu_count > 0:
                print(f"{GREEN}✓ WMI检测成功，找到 {gpu_count} 个GPU{END}")
                return True
            else:
                print(f"{RED}× WMI未返回有效GPU数据{END}")
                return False
        else:
            print(f"{RED}× WMI未返回有效数据{END}")
            return False
    
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"{RED}× WMI调用失败: {str(e)}{END}")
        return False

def check_gputil():
    """使用GPUtil库检测NVIDIA GPU"""
    print(f"\n{BOLD}=== 使用GPUtil测试 ==={END}")
    
    if not HAS_GPUTIL:
        print(f"{RED}× 未安装GPUtil库{END}")
        return False
    
    try:
        gpus = GPUtil.getGPUs()
        
        if gpus:
            print(f"{GREEN}检测到 {len(gpus)} 个NVIDIA GPU:{END}")
            
            for i, gpu in enumerate(gpus):
                print(f"  GPU {i}: {gpu.name}")
                print(f"    ID: {gpu.id}")
                print(f"    UUID: {gpu.uuid}")
                print(f"    负载: {gpu.load*100:.1f}%")
                print(f"    总显存: {gpu.memoryTotal} MB")
                print(f"    已用显存: {gpu.memoryUsed} MB")
                print(f"    可用显存: {gpu.memoryFree} MB")
                print(f"    温度: {gpu.temperature}°C")
            
            print(f"{GREEN}✓ GPUtil检测成功{END}")
            return True
        else:
            print(f"{RED}× GPUtil未检测到NVIDIA GPU{END}")
            return False
    
    except Exception as e:
        print(f"{RED}× GPUtil检测失败: {str(e)}{END}")
        return False

def check_pynvml():
    """使用PyNVML库检测NVIDIA GPU"""
    print(f"\n{BOLD}=== 使用PyNVML测试 ==={END}")
    
    if not HAS_PYNVML:
        print(f"{RED}× 未安装PyNVML库{END}")
        return False
    
    try:
        pynvml.nvmlInit()
        driver_version = pynvml.nvmlSystemGetDriverVersion().decode() if hasattr(pynvml.nvmlSystemGetDriverVersion(), 'decode') else pynvml.nvmlSystemGetDriverVersion()
        print(f"NVIDIA驱动版本: {driver_version}")
        
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            print(f"{GREEN}检测到 {device_count} 个NVIDIA GPU:{END}")
            
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle).decode() if hasattr(pynvml.nvmlDeviceGetName(handle), 'decode') else pynvml.nvmlDeviceGetName(handle)
                
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_memory = memory_info.total / (1024 * 1024)
                used_memory = memory_info.used / (1024 * 1024)
                free_memory = memory_info.free / (1024 * 1024)
                
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                print(f"  GPU {i}: {name}")
                print(f"    总显存: {total_memory:.2f} MB")
                print(f"    已用显存: {used_memory:.2f} MB")
                print(f"    可用显存: {free_memory:.2f} MB")
                print(f"    温度: {temperature}°C")
            
            print(f"{GREEN}✓ PyNVML检测成功{END}")
            pynvml.nvmlShutdown()
            return True
        else:
            pynvml.nvmlShutdown()
            print(f"{RED}× PyNVML未检测到NVIDIA GPU{END}")
            return False
    
    except Exception as e:
        try:
            pynvml.nvmlShutdown()
        except:
            pass
        print(f"{RED}× PyNVML检测失败: {str(e)}{END}")
        return False

def check_pycuda():
    """使用PyCUDA库检测CUDA设备"""
    print(f"\n{BOLD}=== 使用PyCUDA测试 ==={END}")
    
    if not HAS_PYCUDA:
        print(f"{RED}× 未安装PyCUDA库{END}")
        return False
    
    try:
        cuda.init()
        device_count = cuda.Device.count()
        
        if device_count > 0:
            print(f"{GREEN}检测到 {device_count} 个CUDA设备:{END}")
            
            for i in range(device_count):
                device = cuda.Device(i)
                attrs = device.get_attributes()
                
                print(f"  设备 {i}: {device.name()}")
                print(f"    计算能力: {device.compute_capability()[0]}.{device.compute_capability()[1]}")
                print(f"    总显存: {device.total_memory() / (1024 * 1024):.2f} MB")
                print(f"    多处理器数量: {attrs[cuda.device_attribute.MULTIPROCESSOR_COUNT]}")
                print(f"    最大线程数/块: {attrs[cuda.device_attribute.MAX_THREADS_PER_BLOCK]}")
                print(f"    时钟频率: {attrs[cuda.device_attribute.CLOCK_RATE] / 1000:.2f} MHz")
            
            print(f"{GREEN}✓ PyCUDA检测成功{END}")
            return True
        else:
            print(f"{RED}× PyCUDA未检测到CUDA设备{END}")
            return False
    
    except Exception as e:
        print(f"{RED}× PyCUDA检测失败: {str(e)}{END}")
        return False

def check_opencl():
    """使用PyOpenCL库检测OpenCL平台和设备"""
    print(f"\n{BOLD}=== 使用PyOpenCL测试 ==={END}")
    
    if not HAS_PYOPENCL:
        print(f"{RED}× 未安装PyOpenCL库{END}")
        return False
    
    try:
        platforms = cl.get_platforms()
        
        if platforms:
            print(f"{GREEN}检测到 {len(platforms)} 个OpenCL平台:{END}")
            
            gpu_found = False
            for i, platform in enumerate(platforms):
                print(f"  平台 {i}: {platform.name}")
                print(f"    版本: {platform.version}")
                print(f"    供应商: {platform.vendor}")
                
                devices = platform.get_devices()
                print(f"    设备数量: {len(devices)}")
                
                for j, device in enumerate(devices):
                    device_type = []
                    if device.type & cl.device_type.CPU:
                        device_type.append("CPU")
                    if device.type & cl.device_type.GPU:
                        device_type.append("GPU")
                        gpu_found = True
                    if device.type & cl.device_type.ACCELERATOR:
                        device_type.append("ACCELERATOR")
                    if device.type & cl.device_type.DEFAULT:
                        device_type.append("DEFAULT")
                    if device.type & cl.device_type.ALL:
                        device_type.append("ALL")
                    
                    print(f"      设备 {j}: {device.name}")
                    print(f"        类型: {' | '.join(device_type)}")
                    print(f"        供应商: {device.vendor}")
                    if hasattr(device, 'driver_version'):
                        print(f"        驱动版本: {device.driver_version}")
                    print(f"        计算单元: {device.max_compute_units}")
                    print(f"        全局内存: {device.global_mem_size / (1024 * 1024):.2f} MB")
                    
                    if "nvidia" in device.vendor.lower() and "gpu" in device_type:
                        print(f"        {GREEN}发现NVIDIA GPU设备!{END}")
            
            if gpu_found:
                print(f"{GREEN}✓ OpenCL检测成功，找到GPU设备{END}")
            else:
                print(f"{YELLOW}⚠ OpenCL检测成功，但未找到GPU设备{END}")
            
            return gpu_found
        else:
            print(f"{RED}× 未检测到OpenCL平台{END}")
            return False
    
    except Exception as e:
        print(f"{RED}× OpenCL检测失败: {str(e)}{END}")
        return False

def check_system_analyzer():
    """使用系统分析器检测GPU"""
    print(f"\n{BOLD}=== 使用系统分析器测试 ==={END}")
    
    try:
        # 尝试导入系统分析器
        sys.path.append(str(Path.cwd()))
        
        print("正在初始化系统分析器...")
        from src.hardware.system_analyzer import SystemAnalyzer
        
        analyzer = SystemAnalyzer()
        print("正在分析系统硬件...")
        analyzer.analyze_system()
        
        system_info = analyzer.get_system_info()
        
        if 'gpu' in system_info and system_info['gpu']:
            gpu_info = system_info['gpu']
            if 'available' in gpu_info and gpu_info['available']:
                print(f"{GREEN}检测到可用GPU: {gpu_info.get('name', 'Unknown')} ({gpu_info.get('vendor', 'Unknown')}){END}")
                
                if 'devices' in gpu_info and gpu_info['devices']:
                    for i, device in enumerate(gpu_info['devices']):
                        print(f"  GPU {i}: {device.get('name', 'Unknown')}")
                        print(f"    供应商: {device.get('vendor', 'Unknown')}")
                        print(f"    类型: {device.get('type', 'Unknown')}")
                        print(f"    显存: {device.get('memory', 'Unknown')} MB")
                        print(f"    驱动版本: {device.get('driver_version', 'Unknown')}")
                
                print(f"  CUDA支持: {'是' if gpu_info.get('cuda_available', False) else '否'}")
                print(f"  OpenCL支持: {'是' if gpu_info.get('opencl_available', False) else '否'}")
                print(f"  FFmpeg硬件加速: {'支持' if gpu_info.get('ffmpeg_support', False) else '不支持'}")
                
                print(f"{GREEN}✓ SystemAnalyzer检测成功{END}")
                return True
            else:
                print(f"{RED}× SystemAnalyzer未检测到可用GPU{END}")
                return False
        else:
            print(f"{RED}× SystemAnalyzer未返回GPU信息{END}")
            return False
    
    except ImportError as e:
        print(f"{RED}× 无法导入SystemAnalyzer: {str(e)}{END}")
        return False
    except Exception as e:
        print(f"{RED}× SystemAnalyzer检测失败: {str(e)}{END}")
        return False

def check_gpu_config():
    """检查GPU配置文件"""
    print(f"\n{BOLD}=== 检查GPU配置文件 ==={END}")
    
    config_path = Path.home() / "VideoMixTool" / "gpu_config.json"
    
    try:
        print("正在加载GPU配置...")
        if not config_path.exists():
            print(f"{RED}× 未找到GPU配置文件: {config_path}{END}")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        hw_accel = config.get('use_hardware_acceleration', False)
        print(f"硬件加速状态: {'已启用' if hw_accel else '已禁用'}")
        
        if hw_accel:
            detected_gpu = config.get('detected_gpu', 'Unknown')
            vendor = config.get('detected_vendor', 'Unknown')
            encoder = config.get('encoder', 'Unknown')
            
            print(f"配置的GPU: {detected_gpu} ({vendor})")
            print(f"配置的编码器: {encoder}")
            
            print("\n配置文件内容:")
            for key, value in config.items():
                print(f"  {key}: {value}")
            
            print(f"{GREEN}✓ GPU配置检查完成{END}")
            return True
        else:
            print(f"{YELLOW}⚠ 硬件加速未启用{END}")
            return False
    
    except Exception as e:
        print(f"{RED}× GPU配置检查失败: {str(e)}{END}")
        return False

def test_gpu_encoding():
    """测试GPU编码能力"""
    print(f"\n{BOLD}=== 测试GPU编码能力 ==={END}")
    
    # 创建测试视频
    input_video = create_test_video()
    if not input_video:
        print(f"{RED}× 无法创建测试视频，跳过编码测试{END}")
        return False
    
    # 测试NVENC编码
    print("\n测试NVENC编码...")
    output_nvenc = TEMP_DIR / "test_output_nvenc.mp4"
    
    nvenc_cmd = [
        "ffmpeg", "-y", "-i", str(input_video), 
        "-c:v", "h264_nvenc", "-preset", "p2", "-b:v", "5000k",
        str(output_nvenc)
    ]
    
    try:
        start_time = time.time()
        
        # 运行编码命令
        print(f"执行命令: {' '.join(nvenc_cmd)}")
        result = subprocess.run(nvenc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 检查结果
        if output_nvenc.exists():
            size = output_nvenc.stat().st_size
            print(f"{GREEN}✓ NVENC编码测试成功! 耗时: {duration:.2f}秒{END}")
            print(f"  输出文件: {output_nvenc}")
            print(f"  文件大小: {format_size(size)}")
            return True
        else:
            print(f"{RED}× NVENC编码测试失败: 输出文件未创建{END}")
            return False
    
    except subprocess.CalledProcessError as e:
        print(f"{RED}× NVENC编码测试失败: FFmpeg返回错误{END}")
        print(f"  错误输出: {e.stderr.decode('utf-8', errors='ignore')}")
        return False
    
    except Exception as e:
        print(f"{RED}× NVENC编码测试失败: {str(e)}{END}")
        return False

def cleanup():
    """清理临时文件"""
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
    except:
        pass

def main():
    """主函数"""
    # 打印标题
    print(f"{BOLD}{BLUE}===== GPU检测测试工具 ====={END}")
    print("此工具将测试GPU检测功能的各个方面\n")
    
    # 打印系统信息
    print(f"操作系统: {platform.system()} {platform.version()}")
    print(f"Python版本: {platform.python_version()}\n")
    
    print(f"{BOLD}开始测试...{END}")
    
    results = {}
    
    # 运行所有测试
    results['nvidia_smi'] = check_nvidia_smi()
    results['wmi'] = check_wmi_gpu()
    results['gputil'] = check_gputil()
    results['pynvml'] = check_pynvml()
    results['pycuda'] = check_pycuda()
    results['opencl'] = check_opencl()
    results['system_analyzer'] = check_system_analyzer()
    results['gpu_config'] = check_gpu_config()
    results['gpu_encoding'] = test_gpu_encoding()
    
    # 打印摘要
    print(f"\n{BOLD}{BLUE}===== 测试结果摘要 ====={END}")
    passed = 0
    for test, result in results.items():
        status = f"{GREEN}✓ 通过{END}" if result else f"{RED}× 失败{END}"
        print(f"{test:<20}: {status}")
        if result:
            passed += 1
    
    print(f"\n总结: 通过 {passed}/{len(results)} 项测试\n")
    
    # 结论
    if passed >= 3:
        print(f"{GREEN}{BOLD}结论: GPU检测功能正常工作!{END}")
    elif passed >= 1:
        print(f"{YELLOW}{BOLD}结论: GPU检测部分功能正常，但存在一些问题。{END}")
    else:
        print(f"{RED}{BOLD}结论: GPU检测功能存在严重问题!{END}")
    
    # 清理
    input("\n按回车键退出...")
    cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，退出测试")
        cleanup()
    except Exception as e:
        print(f"\n{RED}测试过程中发生错误: {str(e)}{END}")
        cleanup() 