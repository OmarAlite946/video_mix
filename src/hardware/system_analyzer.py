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

class SystemAnalyzer:
    """系统硬件分析器，用于检测系统硬件配置"""
    
    def __init__(self):
        self.system_info = {}
    
    def analyze(self):
        """
        分析系统硬件配置
        
        Returns:
            dict: 系统硬件信息
        """
        # 基本系统信息
        self._analyze_system()
        
        # CPU信息
        self._analyze_cpu()
        
        # 内存信息
        self._analyze_memory()
        
        # GPU信息
        self._analyze_gpu()
        
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
    
    def _analyze_gpu(self):
        """分析GPU信息"""
        gpu_info = {'available': False}
        
        # 检查是否有CUDA设备
        if HAS_GPUTIL:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_info['available'] = True
                    gpu_info['count'] = len(gpus)
                    
                    # 获取第一个GPU的信息
                    gpu = gpus[0]
                    gpu_info['name'] = gpu.name
                    gpu_info['memory_total'] = gpu.memoryTotal
                    gpu_info['memory_used'] = gpu.memoryUsed
                    gpu_info['memory_free'] = gpu.memoryFree
                    gpu_info['memory_util'] = gpu.memoryUtil * 100
                    gpu_info['gpu_util'] = gpu.load * 100
                    gpu_info['temperature'] = gpu.temperature
                    
                    # 多GPU情况
                    if len(gpus) > 1:
                        gpu_info['all_gpus'] = []
                        for i, g in enumerate(gpus):
                            gpu_info['all_gpus'].append({
                                'index': i,
                                'name': g.name,
                                'memory_total': g.memoryTotal,
                                'memory_util': g.memoryUtil * 100
                            })
            except Exception as e:
                gpu_info['error'] = str(e)
        
        # 如果GPUtil无法使用，尝试使用系统命令
        if not gpu_info['available']:
            # NVIDIA GPU
            try:
                if platform.system() == 'Windows':
                    nvidia_smi = subprocess.check_output(['nvidia-smi', '-L'], shell=True, stderr=subprocess.PIPE).decode('utf-8')
                else:
                    nvidia_smi = subprocess.check_output(['nvidia-smi', '-L'], stderr=subprocess.PIPE).decode('utf-8')
                
                if nvidia_smi:
                    gpu_count = nvidia_smi.count('GPU')
                    gpu_info['available'] = True
                    gpu_info['count'] = gpu_count
                    gpu_info['vendor'] = 'NVIDIA'
                    
                    # 提取GPU型号
                    matches = re.findall(r'GPU \d+: (.*) \(', nvidia_smi)
                    if matches:
                        gpu_info['name'] = matches[0]
            except Exception:
                pass
            
            # AMD GPU (Windows)
            if not gpu_info['available'] and platform.system() == 'Windows':
                try:
                    wmic_output = subprocess.check_output('wmic path win32_VideoController get name', shell=True).decode('utf-8')
                    for line in wmic_output.splitlines():
                        if 'AMD' in line or 'Radeon' in line:
                            gpu_info['available'] = True
                            gpu_info['vendor'] = 'AMD'
                            gpu_info['name'] = line.strip()
                            break
                except Exception:
                    pass
            
            # 集成显卡
            if not gpu_info['available']:
                try:
                    if platform.system() == 'Windows':
                        wmic_output = subprocess.check_output('wmic path win32_VideoController get name', shell=True).decode('utf-8')
                        for line in wmic_output.splitlines():
                            if line.strip() and 'wmic' not in line.lower() and 'name' not in line.lower():
                                gpu_info['available'] = True
                                gpu_info['name'] = line.strip()
                                
                                if 'intel' in line.lower():
                                    gpu_info['vendor'] = 'Intel'
                                elif 'nvidia' in line.lower():
                                    gpu_info['vendor'] = 'NVIDIA'
                                elif 'amd' in line.lower() or 'radeon' in line.lower():
                                    gpu_info['vendor'] = 'AMD'
                                else:
                                    gpu_info['vendor'] = 'Unknown'
                                
                                break
                except Exception:
                    pass
        
        self.system_info['gpu'] = gpu_info
    
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