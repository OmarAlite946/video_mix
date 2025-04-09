#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GPU硬件加速配置模块
用于管理视频编码过程中的硬件加速配置
"""

import os
import json
import logging
from pathlib import Path
import re

from .system_analyzer import SystemAnalyzer

# 日志设置
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "use_hardware_acceleration": False,
    "encoder": "libx264",
    "decoder": "",
    "encoding_preset": "medium",
    "extra_params": {},
    "detected_gpu": "",
    "detected_vendor": "",
    "compatibility_mode": True,  # 确保兼容模式默认启用
    "driver_version": ""        # 新增：驱动版本记录
}

# 配置文件路径
CONFIG_DIR = Path.home() / "VideoMixTool"
CONFIG_FILE = CONFIG_DIR / "gpu_config.json"


class GPUConfig:
    """GPU硬件加速配置管理类"""
    
    def __init__(self):
        """初始化GPU配置类"""
        # 默认配置
        self.config = {
            "use_hardware_acceleration": False,  # 使用统一的键名
            "gpu_hardware": None,
            "encoder": None,
            "compatibility_mode": True  # 默认开启兼容模式以提高兼容性
        }
        
        # GPU检测标志
        self.gpu_detected = False
        self.detection_error = None
        
        # 加载已有配置
        self.load_config()
    
    def _load_config(self):
        """从配置文件加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 更新配置，保留默认值
                    for key, value in loaded_config.items():
                        if key in self.config:
                            self.config[key] = value
                logger.info(f"已从 {CONFIG_FILE} 加载GPU配置")
            else:
                # 如果配置文件不存在，创建默认配置
                self._save_config()
        except Exception as e:
            logger.error(f"加载GPU配置出错: {e}")
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存GPU配置到 {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"保存GPU配置出错: {e}")
    
    def detect_and_set_optimal_config(self):
        """
        检测GPU并设置最优配置
        
        Returns:
            bool: 是否成功应用硬件加速
        """
        try:
            analyzer = SystemAnalyzer()
            system_info = analyzer.analyze()
            gpu_info = system_info.get('gpu', {})
            
            # 检查是否有可用GPU
            if not gpu_info.get('available', False):
                logger.info("未检测到可用GPU，将使用CPU编码")
                self._set_cpu_config()
                return False
            
            # 判断是否是NVIDIA GPU - 针对远程桌面会话优化
            primary_vendor = gpu_info.get('primary_vendor', '').lower()
            primary_gpu = gpu_info.get('primary_gpu', '')
            
            # 远程会话检测 - 常见远程桌面软件在GPU检测中会显示为"Microsoft Remote Display Adapter"或类似名称
            remote_session = any(remote in primary_vendor.lower() for remote in ['microsoft', 'remote', 'oray', 'rdp', 'virtual', 'unknown', 'basic'])
            
            if 'nvidia' in primary_vendor:
                # 直接设置NVIDIA配置
                self._set_nvidia_config_direct()
                logger.info(f"检测到NVIDIA GPU: {primary_gpu}")
                return True
            
            # 如果是远程会话，尝试使用nvidia-smi确认是否有NVIDIA卡
            if remote_session or self._check_nvidia_gpu_available():
                logger.info("检测到可能的远程会话或通过nvidia-smi确认存在NVIDIA GPU")
                self._set_nvidia_config_direct()
                logger.info("已设置NVIDIA硬件加速")
                return True
            
            # 检查FFmpeg兼容性
            ffmpeg_compat = gpu_info.get('ffmpeg_compatibility', {})
            
            # 检查是否有FFmpeg兼容性错误
            if 'error' in ffmpeg_compat:
                logger.warning(f"FFmpeg兼容性检测错误: {ffmpeg_compat.get('error')}")
                
                # 如果是因为FFmpeg不可用，尝试根据GPU类型设置常见的编码器
                if any(x in ffmpeg_compat.get('error', '') for x in ["FFmpeg不可用", "无法访问", "未安装"]):
                    logger.info("FFmpeg不可用或无法访问，尝试基于GPU类型设置默认编码器")
                    return self._set_config_without_ffmpeg(gpu_info)
                
                # 其他错误，使用CPU编码
                logger.warning("由于FFmpeg兼容性问题，将使用CPU编码")
                self._set_cpu_config()
                return False
            
            if not ffmpeg_compat.get('hardware_acceleration', False):
                logger.info("检测到GPU但不支持FFmpeg硬件加速，将使用CPU处理")
                self._set_cpu_config()
                return False
            
            # 获取推荐编码器
            encoders = ffmpeg_compat.get('recommended_encoders', [])
            decoders = ffmpeg_compat.get('recommended_decoders', [])
            
            if not encoders:
                logger.info("未检测到支持的硬件编码器，将使用CPU编码")
                self._set_cpu_config()
                return False
            
            # 设置GPU配置
            self.config['use_hardware_acceleration'] = True
            self.config['encoder'] = encoders[0]  # 使用第一个推荐编码器
            self.config['detected_gpu'] = primary_gpu
            self.config['detected_vendor'] = gpu_info.get('primary_vendor', '未知')
            
            if decoders:
                self.config['decoder'] = decoders[0]  # 使用第一个推荐解码器
            
            # 根据GPU类型设置额外参数
            vendor_lower = self.config['detected_vendor'].lower()
            if 'nvidia' in vendor_lower:
                self._set_nvidia_config()
            elif 'amd' in vendor_lower:
                self._set_amd_config()
            elif 'intel' in vendor_lower:
                self._set_intel_config()
            else:
                # 未知厂商，尝试检测通用参数
                logger.info(f"未知GPU厂商: {self.config['detected_vendor']}，尝试根据编码器确定")
                if 'nvenc' in self.config['encoder']:
                    self._set_nvidia_config()
                elif 'amf' in self.config['encoder']:
                    self._set_amd_config()
                elif 'qsv' in self.config['encoder']:
                    self._set_intel_config()
            
            # 保存配置
            self._save_config()
            
            logger.info(f"已应用硬件加速配置: {primary_gpu} ({self.config['detected_vendor']})")
            logger.info(f"使用编码器: {self.config['encoder']}")
            
            return True
            
        except Exception as e:
            logger.error(f"配置硬件加速时出错: {str(e)}")
            logger.exception("详细错误信息:")  # 记录详细的堆栈信息
            self._set_cpu_config()
            return False
    
    def _check_nvidia_gpu_available(self):
        """
        检查系统是否有可用的NVIDIA GPU
        即使在远程桌面会话中，nvidia-smi可能仍然可以访问实际的GPU
        """
        try:
            # 使用nvidia-smi命令检查NVIDIA GPU
            import subprocess
            
            try:
                process = subprocess.Popen(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    output = stdout.decode('utf-8', errors='ignore')
                    
                    # 如果成功获取nvidia-smi输出，说明NVIDIA GPU可用
                    if 'NVIDIA-SMI' in output and 'Driver Version' in output:
                        # 尝试提取GPU名称
                        gpu_name = "NVIDIA GPU"
                        gpu_match = re.search(r'\|\s+(\d+)MiB\s+/\s+(\d+)MiB\s+\|\s+(\d+)%\s+.+\|\s+(.*?)\s+\|', output)
                        if gpu_match and gpu_match.group(4):
                            gpu_name = gpu_match.group(4).strip()
                        
                        # 更新GPU信息
                        self.config['detected_gpu'] = gpu_name
                        self.config['detected_vendor'] = 'NVIDIA'
                        return True
                except subprocess.TimeoutExpired:
                    process.kill()
                    pass
            except Exception:
                pass
                
            # 尝试另一种方式检测
            try:
                process = subprocess.Popen(['nvidia-smi', '-L'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                    output = stdout.decode('utf-8', errors='ignore')
                    
                    if 'GPU 0' in output:
                        # 尝试提取GPU名称
                        match = re.search(r'GPU 0: (.*?)(?:\(UUID:|$)', output)
                        if match:
                            self.config['detected_gpu'] = match.group(1).strip()
                            self.config['detected_vendor'] = 'NVIDIA'
                            return True
                except subprocess.TimeoutExpired:
                    process.kill()
                    pass
            except Exception:
                pass
                
            return False
        except Exception:
            return False
            
    def _set_nvidia_config_direct(self):
        """直接设置NVIDIA GPU加速，无需深度检测"""
        self.config['use_hardware_acceleration'] = True
        self.config['encoder'] = 'h264_nvenc'
        self.config['decoder'] = 'h264_cuvid'
        self.config['compatibility_mode'] = True  # 确保兼容模式启用
        self._set_nvidia_config()
        self._save_config()
    
    def _set_config_without_ffmpeg(self, gpu_info):
        """
        在FFmpeg不可用的情况下，根据GPU类型设置常见的编码器
        
        Args:
            gpu_info: GPU信息字典
            
        Returns:
            bool: 是否成功应用硬件加速
        """
        try:
            primary_gpu = gpu_info.get('primary_gpu', '未知')
            primary_vendor = gpu_info.get('primary_vendor', '未知').lower()
            
            self.config['use_hardware_acceleration'] = True
            self.config['detected_gpu'] = primary_gpu
            self.config['detected_vendor'] = gpu_info.get('primary_vendor', '未知')
            self.config['compatibility_mode'] = True  # 确保兼容模式启用
            
            # 检查是否有任何GPU厂商标识
            vendor_keywords = {
                'nvidia': ['nvidia', 'geforce', 'quadro', 'rtx', 'gtx'],
                'amd': ['amd', 'radeon', 'rx', 'vega', 'firepro'],
                'intel': ['intel', 'iris', 'hd graphics', 'uhd graphics']
            }
            
            # 尝试从GPU名称识别厂商
            gpu_name = primary_gpu.lower()
            detected_vendor = None
            
            for vendor, keywords in vendor_keywords.items():
                if any(keyword in primary_vendor for keyword in keywords) or any(keyword in gpu_name for keyword in keywords):
                    detected_vendor = vendor
                    break
            
            # 尝试特殊检测NVIDIA卡（通常能够通过nvidia-smi检测到）
            if detected_vendor is None and self._check_nvidia_gpu_available():
                detected_vendor = 'nvidia'
                logger.info("通过nvidia-smi确认存在NVIDIA GPU")
            
            # 根据GPU厂商设置常见的编码器
            if detected_vendor == 'nvidia' or 'nvidia' in primary_vendor:
                self.config['encoder'] = 'h264_nvenc'
                self.config['decoder'] = 'h264_cuvid'
                self._set_nvidia_config()
                logger.info(f"FFmpeg不可用，基于NVIDIA GPU设置默认编码器: {self.config['encoder']}")
            elif detected_vendor == 'amd' or 'amd' in primary_vendor or 'radeon' in primary_vendor:
                self.config['encoder'] = 'h264_amf'
                self.config['decoder'] = ''
                self._set_amd_config()
                logger.info(f"FFmpeg不可用，基于AMD GPU设置默认编码器: {self.config['encoder']}")
            elif detected_vendor == 'intel' or 'intel' in primary_vendor:
                self.config['encoder'] = 'h264_qsv'
                self.config['decoder'] = 'h264_qsv'
                self._set_intel_config()
                logger.info(f"FFmpeg不可用，基于Intel GPU设置默认编码器: {self.config['encoder']}")
            else:
                # 未知GPU厂商，尝试识别通用显卡
                logger.info(f"未知GPU厂商: {primary_vendor}, 显卡: {primary_gpu}")
                logger.info("尝试根据系统信息检测可能的GPU类型")
                
                # 尝试从其他来源获取信息
                import platform
                import subprocess
                
                try:
                    # 在Windows上尝试使用dxdiag获取显卡信息
                    if platform.system() == 'Windows':
                        logger.info("尝试使用dxdiag获取GPU信息")
                        temp_file = os.path.join(os.environ.get('TEMP', '.'), 'dxdiag_output.txt')
                        subprocess.run(['dxdiag', '/t', temp_file], shell=True, timeout=10)
                        
                        if os.path.exists(temp_file):
                            with open(temp_file, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                                if 'nvidia' in content or 'geforce' in content:
                                    self.config['encoder'] = 'h264_nvenc'
                                    self.config['decoder'] = 'h264_cuvid'
                                    self._set_nvidia_config()
                                    logger.info("通过dxdiag检测到NVIDIA GPU")
                                    self._save_config()
                                    return True
                                elif 'amd' in content or 'radeon' in content:
                                    self.config['encoder'] = 'h264_amf'
                                    self._set_amd_config()
                                    logger.info("通过dxdiag检测到AMD GPU")
                                    self._save_config()
                                    return True
                                elif 'intel' in content and ('graphics' in content or 'iris' in content):
                                    self.config['encoder'] = 'h264_qsv'
                                    self.config['decoder'] = 'h264_qsv'
                                    self._set_intel_config()
                                    logger.info("通过dxdiag检测到Intel集成显卡")
                                    self._save_config()
                                    return True
                except Exception as e:
                    logger.warning(f"使用dxdiag获取GPU信息失败: {str(e)}")
                
                # 如果所有检测都失败，使用CPU编码
                logger.info("无法确定GPU类型，将使用CPU编码")
                self._set_cpu_config()
                return False
            
            # 保存配置
            self._save_config()
            
            logger.info(f"已应用硬件加速配置: {primary_gpu} ({self.config['detected_vendor']})")
            logger.info(f"使用编码器: {self.config['encoder']}")
            
            return True
        except Exception as e:
            logger.error(f"在FFmpeg不可用的情况下配置硬件加速时出错: {str(e)}")
            logger.exception("详细错误信息:")
            self._set_cpu_config()
            return False
    
    def _set_cpu_config(self):
        """设置CPU编码配置"""
        self.config['use_hardware_acceleration'] = False
        self.config['encoder'] = 'libx264'
        self.config['decoder'] = ''
        self.config['encoding_preset'] = 'medium'
        self.config['extra_params'] = {}
        self._save_config()
    
    def _set_nvidia_config(self):
        """设置NVIDIA GPU的特定配置"""
        # 对于兼容模式使用p4预设，否则使用p2
        preset = 'p4' if self.config['compatibility_mode'] or 'hevc' in self.config['encoder'] else 'p2'
        self.config['encoding_preset'] = preset
        
        # 检测驱动版本（保持现有功能）
        self._detect_driver_version()
        
        # 设置适合兼容模式的参数
        # 简化兼容模式参数，避免使用复杂参数
        self.config['extra_params'] = {
            'spatial-aq': '1',  # 基础空间自适应量化
            'temporal-aq': '1'  # 基础时间自适应量化
        }
        
        # 兼容模式下不添加可能导致问题的高级参数
        if not self.config['compatibility_mode']:
            # 只在非兼容模式下添加高级参数
            self.config['extra_params'].update({
                'rc': 'vbr_hq',     # 高质量可变比特率模式
                'cq': '23',         # 质量参数
                'refs': '3',        # 参考帧数量
                'b_ref_mode': 'middle'  # B帧参考模式
            })
        
        logger.info(f"NVIDIA GPU编码器设置为兼容模式: {self.config['compatibility_mode']}")
        logger.info(f"使用预设: {preset}")
        logger.info(f"编码参数: {self.config['extra_params']}")
    
    def _detect_driver_version(self):
        """检测NVIDIA驱动版本并记录"""
        try:
            import subprocess
            process = subprocess.Popen(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            stdout, stderr = process.communicate(timeout=3)
            version = stdout.decode('utf-8', errors='ignore').strip()
            
            if version:
                self.config['driver_version'] = version
                logger.info(f"检测到NVIDIA驱动版本: {version}")
                
                # 自动确定是否需要兼容模式
                # 如果驱动版本低于 516.xx，启用兼容模式
                try:
                    major_version = float(version.split('.')[0])
                    if major_version < 516:
                        self.config['compatibility_mode'] = True
                        logger.info(f"驱动版本 {version} 较旧，自动启用兼容模式")
                    else:
                        self.config['compatibility_mode'] = False
                        logger.info(f"驱动版本 {version} 较新，使用标准模式")
                except (ValueError, IndexError):
                    # 如果无法解析版本号，默认使用兼容模式
                    self.config['compatibility_mode'] = True
                    logger.info("无法解析驱动版本，默认启用兼容模式")
        except Exception as e:
            logger.warning(f"检测NVIDIA驱动版本时出错: {e}")
            # 出错时默认使用兼容模式
            self.config['compatibility_mode'] = True
    
    def _set_amd_config(self):
        """设置AMD GPU的特定配置"""
        self.config['encoding_preset'] = 'quality'
        self.config['extra_params'] = {
            'quality': 'balanced',
            'usage': 'transcoding'
        }
    
    def _set_intel_config(self):
        """设置Intel GPU的特定配置"""
        self.config['encoding_preset'] = 'medium'
        self.config['extra_params'] = {
            'look_ahead': '1',
            'global_quality': '20'
        }
    
    def get_ffmpeg_params(self):
        """
        获取FFmpeg参数
        
        Returns:
            dict: FFmpeg参数字典
        """
        params = {
            'vcodec': self.config['encoder'],
            'preset': self.config['encoding_preset'],
        }
        
        # 如果启用了硬件加速，添加额外参数
        if self.config['use_hardware_acceleration']:
            for key, value in self.config['extra_params'].items():
                params[key] = value
        
        return params
    
    def is_hardware_acceleration_enabled(self):
        """
        检查是否启用了硬件加速
        
        Returns:
            bool: 是否启用硬件加速
        """
        # 兼容两种可能的键名
        if 'use_hardware_acceleration' in self.config:
            return self.config['use_hardware_acceleration']
        elif 'hardware_acceleration' in self.config:
            return self.config['hardware_acceleration']
        return False
    
    def get_gpu_info(self):
        """
        获取当前配置中的GPU信息
        
        Returns:
            tuple: (GPU名称, GPU厂商)
        """
        gpu_name = self.config.get('detected_gpu', '')
        if not gpu_name and 'primary_gpu' in self.config:
            gpu_name = self.config.get('primary_gpu', 'NVIDIA GPU')
        
        gpu_vendor = self.config.get('detected_vendor', '')
        if not gpu_vendor and 'primary_vendor' in self.config:
            gpu_vendor = self.config.get('primary_vendor', 'NVIDIA')
        
        # 如果仍然没有值，提供默认值
        if not gpu_name:
            gpu_name = "NVIDIA GPU"
        if not gpu_vendor:
            gpu_vendor = "NVIDIA"
        
        return (gpu_name, gpu_vendor)
    
    def get_encoder(self):
        """
        获取当前配置的编码器
        
        Returns:
            str: 编码器名称
        """
        encoder = self.config.get('encoder', None)
        if not encoder:
            # 如果没有设置编码器，根据厂商确定默认值
            _, vendor = self.get_gpu_info()
            if 'nvidia' in vendor.lower():
                return 'h264_nvenc'
            elif 'amd' in vendor.lower():
                return 'h264_amf'
            elif 'intel' in vendor.lower():
                return 'h264_qsv'
            else:
                return 'libx264'
        return encoder
    
    def set_compatibility_mode(self, enabled):
        """设置兼容模式状态
        
        Args:
            enabled (bool): 是否启用兼容模式
            
        Returns:
            bool: 设置是否成功，只有检测到NVIDIA显卡时才能设置
        """
        # 只有使用NVIDIA显卡时才需要兼容模式
        if self.config.get("gpu_hardware") == "nvidia":
            self.config["compatibility_mode"] = bool(enabled)
            self.save_config()
            logging.info(f"NVIDIA GPU兼容模式已{'启用' if enabled else '禁用'}")
            return True
        else:
            logging.warning("无法设置兼容模式：未检测到NVIDIA显卡")
            return False
    
    def is_compatibility_mode_enabled(self):
        """检查兼容模式是否启用"""
        return self.config.get("compatibility_mode", True)  # 默认为True
    
    def get_nvidia_parameters(self):
        """获取NVIDIA编码参数，根据兼容模式返回不同参数"""
        if self.is_compatibility_mode_enabled():
            # 兼容模式参数，适用于旧版驱动
            return [
                "-c:v", "h264_nvenc",
                "-preset", "p4",  # 使用更兼容的preset
                "-profile:v", "main",
                "-b:v", "5M"
            ]
        else:
            # 标准模式参数，使用高级特性
            return [
                "-c:v", "h264_nvenc",
                "-preset", "p2",  # 性能和质量平衡
                "-tune", "hq",
                "-profile:v", "high",
                "-rc", "vbr",  # 可变码率
                "-cq", "19",   # 恒定质量参数
                "-b:v", "5M"
            ]
    
    def load_config(self):
        """加载配置"""
        self._load_config()
    
    def save_config(self):
        """保存配置"""
        self._save_config() 