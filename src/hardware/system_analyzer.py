#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统硬件信息分析模块
"""

import os
import sys
import platform
import subprocess
import re
import psutil
from pathlib import Path

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# 添加新的GPU相关库导入
try:
    import pycuda.driver as cuda
    HAS_PYCUDA = True
except ImportError:
    HAS_PYCUDA = False

try:
    import pyopencl as cl
    HAS_OPENCL = True
except ImportError:
    HAS_OPENCL = False

# 确保添加GPU相关依赖
REQUIRED_DEPENDENCIES = [
    "psutil",
    "GPUtil"
]

OPTIONAL_DEPENDENCIES = [
    "numpy",
    "pycuda",
    "pyopencl"
]

class SystemAnalyzer:
    """系统硬件分析器，用于检测系统硬件配置"""
    
    def __init__(self, deep_gpu_detection=False):
        self.system_info = {}
        self.deep_gpu_detection = deep_gpu_detection
    
    def analyze(self, deep_gpu_detection=None):
        """
        分析系统硬件配置
        
        Args:
            deep_gpu_detection: 是否进行深度GPU检测，会消耗较多时间
        
        Returns:
            dict: 系统硬件信息
        """
        # 如果传入参数，更新检测级别
        if deep_gpu_detection is not None:
            self.deep_gpu_detection = deep_gpu_detection
            
        # 基本系统信息
        self._analyze_system()
        
        # CPU信息
        self._analyze_cpu()
        
        # 内存信息
        self._analyze_memory()
        
        # GPU信息 - 先快速检测基本信息
        self._analyze_gpu_basic()
        
        # 如果需要深度检测，执行详细检测
        if self.deep_gpu_detection:
            self._analyze_gpu_deep()
        
        # 存储信息
        self._analyze_storage()
        
        # FFmpeg检测
        self._check_ffmpeg()
        
        return self.system_info
    
    def _analyze_system(self):
        """分析基本系统信息"""
        self.system_info['os'] = platform.system()
        self.system_info['os_version'] = platform.version()
        self.system_info['platform'] = platform.platform()
        self.system_info['python_version'] = platform.python_version()
        self.system_info['hostname'] = platform.node()
        
        if self.system_info['os'] == 'Windows':
            try:
                winver = sys.getwindowsversion()
                self.system_info['windows_version'] = f"{winver.major}.{winver.minor}.{winver.build}"
            except Exception as e:
                self.system_info['windows_version'] = "Unknown"
    
    def _analyze_cpu(self):
        """分析CPU信息"""
        cpu_info = {}
        
        # CPU核心数
        cpu_info['cores_physical'] = psutil.cpu_count(logical=False)
        cpu_info['cores_logical'] = psutil.cpu_count(logical=True)
        
        # CPU使用率
        cpu_info['usage_percent'] = psutil.cpu_percent(interval=0.5)
        
        # CPU频率
        if hasattr(psutil, 'cpu_freq'):
            freq = psutil.cpu_freq()
            if freq:
                cpu_info['frequency_current'] = freq.current
                if hasattr(freq, 'max') and freq.max:
                    cpu_info['frequency_max'] = freq.max
        
        # CPU型号（平台特定）
        if platform.system() == 'Windows':
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                cpu_info['model'] = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                winreg.CloseKey(key)
            except Exception:
                cpu_info['model'] = platform.processor()
        elif platform.system() == 'Linux':
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            cpu_info['model'] = line.split(':')[1].strip()
                            break
            except Exception:
                cpu_info['model'] = platform.processor()
        else:
            cpu_info['model'] = platform.processor()
        
        self.system_info['cpu'] = cpu_info
    
    def _analyze_memory(self):
        """分析内存信息"""
        memory_info = {}
        
        # 系统内存
        mem = psutil.virtual_memory()
        memory_info['total'] = mem.total
        memory_info['available'] = mem.available
        memory_info['used'] = mem.used
        memory_info['percent'] = mem.percent
        
        # 转换为GB
        memory_info['total_gb'] = round(mem.total / (1024 ** 3), 2)
        memory_info['available_gb'] = round(mem.available / (1024 ** 3), 2)
        memory_info['used_gb'] = round(mem.used / (1024 ** 3), 2)
        
        # 交换内存
        swap = psutil.swap_memory()
        memory_info['swap_total'] = swap.total
        memory_info['swap_used'] = swap.used
        memory_info['swap_free'] = swap.free
        memory_info['swap_percent'] = swap.percent
        
        self.system_info['memory'] = memory_info
    
    def _analyze_gpu_basic(self):
        """
        快速分析GPU基本信息 - 优先使用系统API直接获取
        """
        gpu_info = {'available': False, 'gpus': [], 'accelerators': {}}
        
        # 标记是否检测到了远程显示驱动
        remote_display_detected = False
        
        # Windows平台优先使用WMI快速获取
        if platform.system() == 'Windows':
            try:
                # 单次WMI调用获取所有显卡信息
                wmi_cmd = 'wmic path win32_VideoController get Name,AdapterRAM,DriverVersion,VideoProcessor,PNPDeviceID /format:list'
                
                # 使用Popen代替check_output，以避免timeout参数问题
                process = subprocess.Popen(wmi_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    wmi_output = stdout.decode('utf-8', errors='ignore')
                    
                    sections = wmi_output.strip().split('\n\n')
                    if sections:
                        for i, section in enumerate(sections):
                            if not section.strip():
                                continue
                            
                            gpu = {'index': i, 'type': 'unknown'}
                            
                            # 提取显卡名称
                            name_match = re.search(r'Name=(.*)', section)
                            if name_match:
                                gpu['name'] = name_match.group(1).strip()
                                
                                # 判断GPU供应商
                                name_lower = gpu['name'].lower()
                                if 'nvidia' in name_lower:
                                    gpu['vendor'] = 'NVIDIA'
                                    gpu['type'] = 'dedicated'
                                elif 'amd' in name_lower or 'radeon' in name_lower:
                                    gpu['vendor'] = 'AMD'
                                    gpu['type'] = 'dedicated'
                                elif 'intel' in name_lower:
                                    gpu['vendor'] = 'Intel'
                                    gpu['type'] = 'integrated'
                                elif 'oray' in name_lower or 'remote' in name_lower or 'vnc' in name_lower or 'rdp' in name_lower:
                                    gpu['vendor'] = 'RemoteDisplay'
                                    gpu['type'] = 'virtual'
                                    remote_display_detected = True
                                else:
                                    gpu['vendor'] = 'Unknown'
                                    # 检查是否可能是远程显示驱动
                                    if 'display' in name_lower or 'virtual' in name_lower or 'remote' in name_lower:
                                        remote_display_detected = True
                            
                            # 提取显存大小
                            ram_match = re.search(r'AdapterRAM=(.*)', section)
                            if ram_match:
                                try:
                                    ram_bytes = int(ram_match.group(1).strip())
                                    gpu['memory_total_mb'] = ram_bytes / (1024 * 1024)
                                except ValueError:
                                    pass
                            
                            # 提取驱动版本
                            driver_match = re.search(r'DriverVersion=(.*)', section)
                            if driver_match:
                                gpu['driver_version'] = driver_match.group(1).strip()
                            
                            gpu_info['gpus'].append(gpu)
                        
                        # 如果找到了GPU，标记为可用
                        if gpu_info['gpus']:
                            gpu_info['available'] = True
                            gpu_info['count'] = len(gpu_info['gpus'])
                            # 设置主GPU信息（第一个GPU）
                            gpu_info['primary_gpu'] = gpu_info['gpus'][0]['name']
                            gpu_info['primary_vendor'] = gpu_info['gpus'][0]['vendor']
                except subprocess.TimeoutExpired:
                    process.kill()
                    print("wmic命令超时")
            except Exception as e:
                pass  # 如果WMI失败，将继续使用其他方法
        
        # 如果检测到远程显示驱动或者未识别显卡类型，尝试使用nvidia-smi命令检测NVIDIA GPU
        has_nvidia_gpu = False
        if remote_display_detected or (gpu_info['available'] and (gpu_info['primary_vendor'] == 'Unknown' or gpu_info['primary_vendor'] == 'RemoteDisplay')):
            try:
                # 使用nvidia-smi检查是否有NVIDIA GPU
                process = subprocess.Popen(['nvidia-smi', '-L'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    nvidia_output = stdout.decode('utf-8', errors='ignore')
                    
                    if 'GPU 0' in nvidia_output:
                        # 找到NVIDIA GPU，解析详细信息
                        nvidia_gpus = []
                        gpu_lines = nvidia_output.strip().split('\n')
                        
                        for i, line in enumerate(gpu_lines):
                            if 'GPU ' in line:
                                # 提取GPU信息，例如：GPU 0: NVIDIA GeForce RTX 3080 (UUID: GPU-...)
                                match = re.search(r'GPU \d+: (.*?)(?:\(UUID:|$)', line)
                                if match:
                                    gpu_name = match.group(1).strip()
                                    
                                    # 获取显存信息
                                    memory_info = {'total_mb': 0}
                                    try:
                                        mem_cmd = f'nvidia-smi --id={i} --query-gpu=memory.total --format=csv,noheader,nounits'
                                        mem_process = subprocess.Popen(mem_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                                        try:
                                            mem_stdout, _ = mem_process.communicate(timeout=2)
                                            memory_total = mem_stdout.decode('utf-8', errors='ignore').strip()
                                            if memory_total.isdigit():
                                                memory_info['total_mb'] = int(memory_total)
                                        except subprocess.TimeoutExpired:
                                            mem_process.kill()
                                    except Exception:
                                        pass
                                    
                                    nvidia_gpu = {
                                        'index': i,
                                        'name': gpu_name,
                                        'vendor': 'NVIDIA',
                                        'memory_total_mb': memory_info['total_mb'],
                                        'type': 'dedicated'
                                    }
                                    nvidia_gpus.append(nvidia_gpu)
                        
                        if nvidia_gpus:
                            has_nvidia_gpu = True
                            # 完全替换之前检测到的显卡信息
                            gpu_info['gpus'] = nvidia_gpus
                            gpu_info['available'] = True
                            gpu_info['count'] = len(nvidia_gpus)
                            gpu_info['primary_gpu'] = nvidia_gpus[0]['name']
                            gpu_info['primary_vendor'] = 'NVIDIA'
                            print(f"检测到NVIDIA显卡: {nvidia_gpus[0]['name']}")
                except subprocess.TimeoutExpired:
                    process.kill()
                    print("nvidia-smi命令超时")
            except Exception as e:
                print(f"尝试检测NVIDIA显卡时出错: {str(e)}")
        
        # Linux平台使用lspci快速检测
        elif platform.system() == 'Linux':
            try:
                # 使用lspci查找VGA控制器
                process = subprocess.Popen(['lspci', '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    output = stdout.decode('utf-8')
                    
                    # 提取所有VGA控制器和3D控制器信息
                    gpu_matches = re.finditer(r'^[0-9a-f:.]+\s+(?:VGA|3D)\s+.*?:([^:]+).*$', output, re.MULTILINE)
                    
                    for i, match in enumerate(gpu_matches):
                        gpu_name = match.group(1).strip()
                        gpu = {'index': i, 'name': gpu_name, 'type': 'unknown'}
                        
                        # 判断GPU供应商
                        if 'nvidia' in gpu_name.lower():
                            gpu['vendor'] = 'NVIDIA'
                            gpu['type'] = 'dedicated'
                        elif 'amd' in gpu_name.lower() or 'radeon' in gpu_name.lower():
                            gpu['vendor'] = 'AMD'
                            gpu['type'] = 'dedicated'
                        elif 'intel' in gpu_name.lower():
                            gpu['vendor'] = 'Intel'
                            gpu['type'] = 'integrated'
                        else:
                            gpu['vendor'] = 'Unknown'
                        
                        gpu_info['gpus'].append(gpu)
                    
                    # 如果找到了GPU，标记为可用
                    if gpu_info['gpus']:
                        gpu_info['available'] = True
                        gpu_info['count'] = len(gpu_info['gpus'])
                        # 设置主GPU信息（第一个GPU）
                        gpu_info['primary_gpu'] = gpu_info['gpus'][0]['name']
                        gpu_info['primary_vendor'] = gpu_info['gpus'][0]['vendor']
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception as e:
                pass  # 如果lspci失败，将继续使用其他方法
        
        # macOS平台使用system_profiler
        elif platform.system() == 'Darwin':
            try:
                process = subprocess.Popen(['system_profiler', 'SPDisplaysDataType'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    output = stdout.decode('utf-8')
                    
                    # macOS平台解析系统输出...
                    # (这里可以实现具体的macOS检测代码)
                except subprocess.TimeoutExpired:
                    process.kill()
            except Exception as e:
                pass
                
        # 如果上述方法都没有检测到GPU，尝试使用GPUtil（仅适用于NVIDIA）
        if not has_nvidia_gpu and HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_info['available'] = True
                    gpu_info['count'] = len(gpus)
                    
                    # 获取所有NVIDIA GPU信息
                    for i, gpu in enumerate(gpus):
                        gpu_data = {
                            'index': i,
                            'name': gpu.name,
                            'vendor': 'NVIDIA',
                            'memory_total_mb': gpu.memoryTotal,
                            'memory_used_mb': gpu.memoryUsed,
                            'memory_free_mb': gpu.memoryFree,
                            'memory_util_percent': round(gpu.memoryUtil * 100, 2),
                            'gpu_util_percent': round(gpu.load * 100, 2),
                            'temperature_c': gpu.temperature,
                            'type': 'dedicated'
                        }
                        gpu_info['gpus'].append(gpu_data)
                    
                    # 设置主GPU信息
                    gpu_info['primary_gpu'] = gpu_info['gpus'][0]['name'] 
                    gpu_info['primary_vendor'] = 'NVIDIA'
            except Exception as e:
                pass
        
        # 将基本GPU信息保存到系统信息中
        self.system_info['gpu'] = gpu_info
    
    def _analyze_gpu_deep(self):
        """
        深度分析GPU信息 - 检测硬件加速能力和兼容性
        """
        # 获取基本GPU信息
        gpu_info = self.system_info.get('gpu', {})
        
        # 如果没有检测到GPU，不进行深度检测
        if not gpu_info.get('available', False):
            return
        
        # 1. 检查CUDA支持
        gpu_info['accelerators']['cuda'] = self._check_cuda_support()
        
        # 2. 检查DirectX支持（仅Windows）
        if platform.system() == 'Windows':
            gpu_info['accelerators']['directx'] = self._check_directx_support()
        
        # 3. 检查OpenCL支持
        gpu_info['accelerators']['opencl'] = self._check_opencl_support()
        
        # 4. 为每个GPU添加编码/解码能力分析
        for i, gpu in enumerate(gpu_info['gpus']):
            gpu_info['gpus'][i]['capabilities'] = self._analyze_gpu_capabilities(gpu)
        
        # 5. 添加FFmpeg兼容性信息
        gpu_info['ffmpeg_compatibility'] = self._analyze_ffmpeg_gpu_compatibility(gpu_info)
        
        # 更新系统信息中的GPU信息
        self.system_info['gpu'] = gpu_info
    
    def _analyze_gpu(self):
        """
        分析GPU信息（向后兼容的方法）
        """
        # 先进行基本检测
        self._analyze_gpu_basic()
        
        # 如果需要深度检测，执行详细检测
        if self.deep_gpu_detection:
            self._analyze_gpu_deep()
    
    def _check_cuda_support(self):
        """检查CUDA支持"""
        cuda_info = {'available': False}
        
        # 方法1：使用pycuda
        if HAS_PYCUDA:
            try:
                cuda.init()
                cuda_info['available'] = True
                cuda_info['version'] = cuda.get_version()
                cuda_info['version_string'] = f"{cuda_info['version'][0]}.{cuda_info['version'][1]}"
                cuda_info['device_count'] = cuda.Device.count()
                return cuda_info
            except Exception as e:
                cuda_info['error_pycuda'] = str(e)
        
        # 方法2：使用nvcc
        try:
            if platform.system() == 'Windows':
                process = subprocess.Popen(['nvcc', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                process = subprocess.Popen(['nvcc', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            stdout, stderr = process.communicate()
            output = stdout.decode('utf-8')
            
            if 'Cuda compilation tools' in output:
                cuda_info['available'] = True
                version_match = re.search(r'release (\d+\.\d+)', output)
                if version_match:
                    cuda_info['version_string'] = version_match.group(1)
                return cuda_info
        except Exception as e:
            cuda_info['error_nvcc'] = str(e)
        
        # 方法3：检查nvidia-smi
        try:
            if platform.system() == 'Windows':
                process = subprocess.Popen(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                process = subprocess.Popen(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            stdout, stderr = process.communicate()
            output = stdout.decode('utf-8')
            
            if 'CUDA Version' in output:
                cuda_info['available'] = True
                version_match = re.search(r'CUDA Version: (\d+\.\d+)', output)
                if version_match:
                    cuda_info['version_string'] = version_match.group(1)
                return cuda_info
        except Exception as e:
            cuda_info['error_smi'] = str(e)
        
        return cuda_info
    
    def _check_opencl_support(self):
        """检查OpenCL支持"""
        opencl_info = {'available': False}
        
        if HAS_OPENCL:
            try:
                platforms = cl.get_platforms()
                if platforms:
                    opencl_info['available'] = True
                    opencl_info['platforms'] = []
                    
                    for platform in platforms:
                        platform_info = {
                            'name': platform.name,
                            'vendor': platform.vendor,
                            'version': platform.version,
                            'devices': []
                        }
                        
                        devices = platform.get_devices()
                        for device in devices:
                            device_info = {
                                'name': device.name,
                                'type': cl.device_type.to_string(device.type),
                                'version': device.version,
                                'driver_version': device.driver_version,
                                'compute_units': device.max_compute_units,
                                'global_memory': device.global_mem_size,
                                'local_memory': device.local_mem_size,
                            }
                            platform_info['devices'].append(device_info)
                        
                        opencl_info['platforms'].append(platform_info)
                    
                    return opencl_info
            except Exception as e:
                opencl_info['error'] = str(e)
        
        # 备用检测方法：通过命令行工具
        try:
            if platform.system() == 'Windows':
                cmd = ['clinfo']  # Windows系统上可能需要安装clinfo
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                cmd = ['clinfo']
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            stdout, stderr = process.communicate()
            output = stdout.decode('utf-8')
            
            if 'Platform Name' in output:
                opencl_info['available'] = True
                opencl_info['detection_method'] = 'clinfo'
        except Exception:
            pass
        
        return opencl_info
    
    def _check_directx_support(self):
        """检查DirectX支持（仅Windows）"""
        directx_info = {'available': False}
        
        if platform.system() != 'Windows':
            directx_info['error'] = "DirectX只在Windows平台可用"
            return directx_info
        
        try:
            # 使用dxdiag检查DirectX
            temp_file = os.path.join(os.environ.get('TEMP', '.'), 'dxdiag_output.txt')
            process = subprocess.Popen(['dxdiag', '/t', temp_file], shell=True)
            process.wait(timeout=10)
            
            # 等待文件生成
            import time
            start_time = time.time()
            while not os.path.exists(temp_file) and time.time() - start_time < 10:
                time.sleep(0.5)
            
            if os.path.exists(temp_file):
                with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # 提取DirectX版本
                    dx_version = re.search(r'DirectX Version: (.*)', content)
                    if dx_version:
                        directx_info['available'] = True
                        directx_info['version'] = dx_version.group(1).strip()
                    
                    # 提取显示适配器信息
                    display_sections = re.findall(r'-------------\r?\nDisplay Devices\r?\n-------------.*?------------', content, re.DOTALL)
                    if display_sections:
                        directx_info['display_devices'] = []
                        for section in display_sections:
                            device = {}
                            
                            card_name = re.search(r'Card name: (.*)', section)
                            if card_name:
                                device['name'] = card_name.group(1).strip()
                            
                            manufacturer = re.search(r'Manufacturer: (.*)', section)
                            if manufacturer:
                                device['manufacturer'] = manufacturer.group(1).strip()
                            
                            chip_type = re.search(r'Chip type: (.*)', section)
                            if chip_type:
                                device['chip_type'] = chip_type.group(1).strip()
                            
                            dac_type = re.search(r'DAC type: (.*)', section)
                            if dac_type:
                                device['dac_type'] = dac_type.group(1).strip()
                            
                            memory = re.search(r'Dedicated Memory: (.*)', section)
                            if memory:
                                device['dedicated_memory'] = memory.group(1).strip()
                            
                            directx_info['display_devices'].append(device)
                
                # 删除临时文件
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
        except Exception as e:
            directx_info['error'] = str(e)
        
        return directx_info
    
    def _analyze_gpu_capabilities(self, gpu):
        """分析GPU的视频处理能力"""
        capabilities = {
            'hardware_encoding': False,
            'hardware_decoding': False,
            'supported_codecs': [],
        }
        
        vendor = gpu.get('vendor', '').lower()
        
        # NVIDIA GPU能力
        if 'nvidia' in vendor:
            # 检查NVENC/NVDEC支持
            try:
                if platform.system() == 'Windows':
                    cmd = 'nvidia-smi -q -d SUPPORTED_CLOCKS'
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                else:
                    cmd = ['nvidia-smi', '-q', '-d', 'SUPPORTED_CLOCKS']
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                stdout, stderr = process.communicate()
                output = stdout.decode('utf-8')
                
                if 'Supported Clocks' in output:
                    # 基本判断是否为足够新的GPU
                    if any(x in gpu.get('name', '').lower() for x in ['gtx', 'rtx', 'quadro', 'tesla']):
                        # GTX 10系列以上或其他新卡通常支持NVENC/NVDEC
                        model_num = re.search(r'(\d{3,4})', gpu.get('name', ''))
                        if model_num and int(model_num.group(1)) >= 1000:
                            capabilities['hardware_encoding'] = True
                            capabilities['hardware_decoding'] = True
                            capabilities['supported_codecs'] = ['h264', 'hevc']
                            
                            # 检测RTX卡是否支持AV1
                            if 'rtx' in gpu.get('name', '').lower() and model_num and int(model_num.group(1)) >= 4000:
                                capabilities['supported_codecs'].append('av1')
            except Exception:
                pass
        
        # AMD GPU能力
        elif 'amd' in vendor or 'radeon' in vendor:
            gpu_name = gpu.get('name', '').lower()
            # 检查VCE/VCN支持
            if any(x in gpu_name for x in ['rx', 'vega', 'radeon vii', 'fury', 'polaris']):
                capabilities['hardware_encoding'] = True
                capabilities['hardware_decoding'] = True
                capabilities['supported_codecs'] = ['h264']
                
                # RX 5000系列及以上支持HEVC
                if re.search(r'rx\s*[5-9]\d{3}', gpu_name) or 'radeon vii' in gpu_name or 'vega' in gpu_name:
                    capabilities['supported_codecs'].append('hevc')
                
                # RX 7000系列可能支持AV1
                if re.search(r'rx\s*[7-9]\d{3}', gpu_name):
                    capabilities['supported_codecs'].append('av1')
        
        # Intel GPU能力
        elif 'intel' in vendor:
            gpu_name = gpu.get('name', '').lower()
            # 检查QuickSync支持
            if any(x in gpu_name for x in ['hd', 'uhd', 'iris']):
                capabilities['hardware_encoding'] = True
                capabilities['hardware_decoding'] = True
                capabilities['supported_codecs'] = ['h264']
                
                # 第7代及以上Intel处理器支持HEVC
                gen_match = re.search(r'gen(\d+)', gpu_name)
                if gen_match and int(gen_match.group(1)) >= 7:
                    capabilities['supported_codecs'].append('hevc')
                
                # 估计Arc和较新的Iris可能支持AV1
                if 'arc' in gpu_name or 'iris xe' in gpu_name:
                    capabilities['supported_codecs'].append('av1')
        
        return capabilities
    
    def _analyze_ffmpeg_gpu_compatibility(self, gpu_info):
        """分析FFmpeg与GPU的兼容性"""
        compatibility = {
            'hardware_acceleration': False,
            'recommended_encoders': [],
            'recommended_decoders': []
        }
        
        # 检查FFmpeg可用性
        if not self.system_info.get('ffmpeg', {}).get('available', False):
            compatibility['error'] = 'FFmpeg不可用，无法分析硬件加速兼容性'
            return compatibility
        
        # 检查主GPU信息
        if not gpu_info.get('available', False) or not gpu_info.get('gpus'):
            compatibility['error'] = '未检测到GPU，无法提供硬件加速支持'
            return compatibility
        
        primary_vendor = gpu_info.get('primary_vendor', '').lower()
        
        # 获取FFmpeg支持的编码器
        try:
            if platform.system() == 'Windows':
                process = subprocess.Popen(['ffmpeg', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                process = subprocess.Popen(['ffmpeg', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            stdout, stderr = process.communicate()
            encoders_output = stdout.decode('utf-8')
            
            # 获取FFmpeg支持的解码器
            if platform.system() == 'Windows':
                process = subprocess.Popen(['ffmpeg', '-decoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                process = subprocess.Popen(['ffmpeg', '-decoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            stdout, stderr = process.communicate()
            decoders_output = stdout.decode('utf-8')
            
            # NVIDIA GPU
            if 'nvidia' in primary_vendor:
                compatibility['hardware_acceleration'] = True
                
                # 检查NVENC编码器
                if 'nvenc' in encoders_output:
                    compatibility['recommended_encoders'].append('h264_nvenc')
                    if 'hevc_nvenc' in encoders_output:
                        compatibility['recommended_encoders'].append('hevc_nvenc')
                
                # 检查NVDEC解码器
                if 'cuvid' in decoders_output:
                    compatibility['recommended_decoders'].append('h264_cuvid')
                    if 'hevc_cuvid' in decoders_output:
                        compatibility['recommended_decoders'].append('hevc_cuvid')
            
            # AMD GPU
            elif 'amd' in primary_vendor:
                compatibility['hardware_acceleration'] = True
                
                # 检查AMF编码器
                if 'amf' in encoders_output:
                    compatibility['recommended_encoders'].append('h264_amf')
                    if 'hevc_amf' in encoders_output:
                        compatibility['recommended_encoders'].append('hevc_amf')
            
            # Intel GPU
            elif 'intel' in primary_vendor:
                compatibility['hardware_acceleration'] = True
                
                # 检查QSV编码器
                if 'qsv' in encoders_output:
                    compatibility['recommended_encoders'].append('h264_qsv')
                    if 'hevc_qsv' in encoders_output:
                        compatibility['recommended_encoders'].append('hevc_qsv')
                
                # 检查QSV解码器
                if 'qsv' in decoders_output:
                    compatibility['recommended_decoders'].append('h264_qsv')
                    if 'hevc_qsv' in decoders_output:
                        compatibility['recommended_decoders'].append('hevc_qsv')
        
        except Exception as e:
            compatibility['error'] = f'分析FFmpeg硬件加速兼容性时出错: {str(e)}'
        
        return compatibility
    
    def _analyze_storage(self):
        """分析存储信息"""
        storage_info = {}
        
        # 获取所有磁盘分区
        partitions = psutil.disk_partitions()
        storage_info['partitions'] = []
        
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partition_info = {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent,
                    'total_gb': round(usage.total / (1024 ** 3), 2),
                    'free_gb': round(usage.free / (1024 ** 3), 2)
                }
                storage_info['partitions'].append(partition_info)
            except Exception:
                # 某些磁盘可能无法访问
                pass
        
        # 简单测试磁盘性能
        try:
            # 创建临时文件
            import tempfile
            import time
            
            temp_dir = tempfile.gettempdir()
            test_file = os.path.join(temp_dir, 'disk_speed_test.bin')
            
            # 写入测试
            start_time = time.time()
            with open(test_file, 'wb') as f:
                f.write(b'0' * 10 * 1024 * 1024)  # 写入10MB数据
            write_time = time.time() - start_time
            write_speed = (10 / write_time) if write_time > 0 else 0
            
            # 读取测试
            start_time = time.time()
            with open(test_file, 'rb') as f:
                data = f.read()
            read_time = time.time() - start_time
            read_speed = (10 / read_time) if read_time > 0 else 0
            
            # 删除临时文件
            os.remove(test_file)
            
            storage_info['io_test'] = {
                'write_speed_mbps': round(write_speed, 2),
                'read_speed_mbps': round(read_speed, 2),
                'test_size_mb': 10
            }
        except Exception:
            pass
        
        self.system_info['storage'] = storage_info
    
    def _check_ffmpeg(self):
        """检查FFmpeg是否可用"""
        ffmpeg_info = {'available': False}
        
        try:
            # 尝试运行ffmpeg -version命令
            if platform.system() == 'Windows':
                process = subprocess.Popen(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                process = subprocess.Popen(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            stdout, stderr = process.communicate()
            output = stdout.decode('utf-8')
            
            if 'ffmpeg version' in output:
                ffmpeg_info['available'] = True
                
                # 提取版本信息
                version_match = re.search(r'ffmpeg version (\S+)', output)
                if version_match:
                    ffmpeg_info['version'] = version_match.group(1)
                
                # 检查编码器支持
                ffmpeg_info['encoders'] = {}
                
                # 检查H.264支持
                if 'libx264' in output:
                    ffmpeg_info['encoders']['h264'] = True
                
                # 检查H.265支持
                if 'libx265' in output:
                    ffmpeg_info['encoders']['h265'] = True
                
                # 检查GPU加速支持
                if 'nvenc' in output or 'nvidia' in output.lower():
                    ffmpeg_info['encoders']['nvenc'] = True
                
                if 'qsv' in output:
                    ffmpeg_info['encoders']['qsv'] = True
                
                if 'amf' in output:
                    ffmpeg_info['encoders']['amf'] = True
        except Exception as e:
            ffmpeg_info['error'] = str(e)
        
        self.system_info['ffmpeg'] = ffmpeg_info
    
    def get_optimal_settings(self):
        """
        根据系统配置推荐最优设置
        
        Returns:
            dict: 推荐设置
        """
        settings = {}
        
        # 分析系统信息（如果尚未分析）
        if not self.system_info:
            self.analyze()
        
        # 推荐硬件加速设置
        if self.system_info.get('gpu', {}).get('available', False):
            gpu_info = self.system_info['gpu']
            
            if gpu_info.get('vendor') == 'NVIDIA':
                settings['hardware_accel'] = 'cuda'
                settings['encoder'] = 'h264_nvenc'
            elif gpu_info.get('vendor') == 'AMD':
                settings['hardware_accel'] = 'amf'
                settings['encoder'] = 'h264_amf'
            elif gpu_info.get('vendor') == 'Intel':
                settings['hardware_accel'] = 'qsv'
                settings['encoder'] = 'h264_qsv'
            else:
                settings['hardware_accel'] = 'none'
                settings['encoder'] = 'libx264'
        else:
            settings['hardware_accel'] = 'none'
            settings['encoder'] = 'libx264'
        
        # 推荐线程数
        cpu_cores = self.system_info.get('cpu', {}).get('cores_logical', 4)
        settings['threads'] = max(1, min(cpu_cores - 1, 16))  # 保留至少一个核心给系统
        
        # 推荐批处理数量
        mem_gb = self.system_info.get('memory', {}).get('total_gb', 8)
        
        if mem_gb >= 32:
            settings['batch_size'] = 50
            settings['mode'] = '高性能模式'
        elif mem_gb >= 16:
            settings['batch_size'] = 30
            settings['mode'] = '平衡模式'
        elif mem_gb >= 8:
            settings['batch_size'] = 15
            settings['mode'] = '资源节约模式'
        else:
            settings['batch_size'] = 5
            settings['mode'] = '超级兼容模式'
        
        # 推荐预览质量
        if settings['mode'] in ['高性能模式', '平衡模式']:
            settings['preview_quality'] = 'high'
        else:
            settings['preview_quality'] = 'low'
        
        # 推荐输出分辨率
        settings['output_resolution'] = '1080p'  # 默认1080p
        
        return settings 