#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频处理核心模块
"""

import os
import time
import random
import shutil
import subprocess
import threading
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple, Callable
import uuid
import datetime
import logging
import sys
import json

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import cv2
    import numpy as np
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx, CompositeAudioClip
except ImportError as e:
    print(f"正在安装必要的依赖...")
    try:
        import pip
        pip.main(["install", "moviepy", "opencv-python", "numpy"])
        import cv2
        import numpy as np
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx, CompositeAudioClip
    except Exception as install_error:
        print(f"安装依赖失败: {install_error}")
        print("请手动安装依赖：")
        print("pip install moviepy opencv-python numpy")
        sys.exit(1)

from utils.logger import get_logger
from utils.cache_config import CacheConfig

logger = get_logger()

class VideoProcessor:
    """视频处理核心类"""
    
    def __init__(self, settings: Dict[str, Any] = None, progress_callback: Callable[[str, float], None] = None):
        """
        初始化视频处理器
        
        Args:
            settings: 处理设置参数
            progress_callback: 进度回调函数，参数为(状态消息, 进度百分比)
        """
        # 初始化设置
        self.settings = settings if settings else {}
        self.progress_callback = progress_callback
        self.stop_requested = False
        self.temp_files = []
        self.start_time = 0
        
        # 进度更新定时器
        self._progress_timer = None
        self._last_progress_message = ""
        self._last_progress_percent = 0
        
        # 初始化日志
        global logger
        if not logger:
            logger = logging.getLogger("VideoProcessor")
        
        # 检查FFmpeg
        self._check_ffmpeg()
        
        # 获取缓存配置
        cache_config = CacheConfig()
        cache_dir = cache_config.get_cache_dir()
        
        # 默认设置
        self.default_settings = {
            "hardware_accel": "auto",  # 硬件加速：auto, cuda, qsv, amf, none
            "encoder": "libx264",       # 视频编码器
            "resolution": "1080p",      # 输出分辨率
            "bitrate": 5000,            # 比特率(kbps)
            "threads": 4,               # 处理线程数
            "transition": "random",     # 转场效果: random, mirror_flip, hue_shift, ...
            "transition_duration": 0.5,  # 转场时长(秒)
            "voice_volume": 1.0,        # 配音音量
            "bgm_volume": 0.5,          # 背景音乐音量
            "output_format": "mp4",     # 输出格式
            "temp_dir": cache_dir,      # 使用配置的缓存目录
            # 添加水印相关默认设置
            "watermark_enabled": False,  # 水印功能默认关闭
            "watermark_prefix": "",      # 默认无自定义前缀
            "watermark_size": 24,        # 默认字体大小24像素
            "watermark_color": "#FFFFFF", # 默认白色
            "watermark_position": "右上角", # 默认位置在右上角
            "watermark_pos_x": 0,        # 默认X轴位置修正
            "watermark_pos_y": 0         # 默认Y轴位置修正
        }
        
        # 更新设置
        self.settings = self.default_settings.copy()
        if settings:
            self.settings.update(settings)
        
        # 确保临时目录存在
        os.makedirs(self.settings["temp_dir"], exist_ok=True)
        
        # 初始化随机数生成器
        random.seed(time.time())
    
    def _check_ffmpeg(self) -> bool:
        """
        检查FFmpeg是否可用
        
        Returns:
            bool: 是否可用
        """
        ffmpeg_cmd = "ffmpeg"
        ffmpeg_path_file = None
        
        # 尝试从ffmpeg_path.txt读取自定义路径
        try:
            # 获取项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent
            ffmpeg_path_file = project_root / "ffmpeg_path.txt"
            
            if ffmpeg_path_file.exists():
                with open(ffmpeg_path_file, 'r', encoding="utf-8") as f:
                    custom_path = f.read().strip()
                    if custom_path and os.path.exists(custom_path):
                        logger.info(f"使用自定义FFmpeg路径: {custom_path}")
                        ffmpeg_cmd = custom_path
                    else:
                        logger.warning(f"自定义FFmpeg路径无效或不存在: {custom_path}")
        except Exception as e:
            logger.error(f"读取自定义FFmpeg路径时出错: {str(e)}")
        
        try:
            # 尝试执行ffmpeg命令
            logger.info(f"正在检查FFmpeg: {ffmpeg_cmd}")
            result = subprocess.run(
                [ffmpeg_cmd, "-version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=5  # 增加超时时间
            )
            
            if result.returncode == 0:
                version_info = result.stdout.splitlines()[0] if result.stdout else "未知版本"
                logger.info(f"FFmpeg可用，版本信息：{version_info}")
                
                # 检查编码器支持
                try:
                    encoders_result = subprocess.run(
                        [ffmpeg_cmd, "-encoders"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5
                    )
                    
                    if encoders_result.returncode == 0:
                        encoders_output = encoders_result.stdout
                        # 检查硬件加速编码器
                        hw_encoders = []
                        for encoder in ["nvenc", "qsv", "amf", "vaapi"]:
                            if encoder in encoders_output:
                                hw_encoders.append(encoder)
                        
                        if hw_encoders:
                            logger.info(f"检测到支持的硬件加速编码器: {', '.join(hw_encoders)}")
                        else:
                            logger.info("未检测到支持的硬件加速编码器")
                except Exception as e:
                    logger.warning(f"检查编码器支持时出错: {str(e)}")
                
                return True
            else:
                error_detail = f"返回码: {result.returncode}, 错误: {result.stderr}"
                logger.error(f"FFmpeg不可用: {error_detail}")
                return False
        except FileNotFoundError:
            if ffmpeg_path_file and ffmpeg_path_file.exists():
                error_msg = f"自定义FFmpeg路径不正确，请重新配置。路径: {ffmpeg_cmd}"
            else:
                error_msg = "FFmpeg不在系统路径中，请安装FFmpeg并确保可以在命令行中使用，或使用配置路径功能"
            logger.error(error_msg)
            return False
        except PermissionError:
            logger.error(f"没有执行FFmpeg的权限: {ffmpeg_cmd}")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"检查FFmpeg超时，可能系统资源不足或FFmpeg无响应")
            return False
        except Exception as e:
            logger.error(f"检查FFmpeg时出错: {str(e)}, 类型: {type(e).__name__}")
            return False
    
    def _format_time(self, seconds):
        """
        将秒数格式化为时:分:秒格式
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化后的时间字符串 (HH:MM:SS)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def report_progress(self, message: str, percent: float):
        """
        报告进度
        
        Args:
            message: 状态消息
            percent: 进度百分比 (0-100)
        """
        if self.progress_callback:
            try:
                # 如果处理已经开始，添加已用时间
                if self.start_time > 0:
                    elapsed_time = time.time() - self.start_time
                    elapsed_str = self._format_time(elapsed_time)
                    message = f"{message} (已用时: {elapsed_str})"
                
                # 保存最后一次进度信息，用于定时器重发
                self._last_progress_message = message
                self._last_progress_percent = percent
                
                # 进度更新应该在主线程中进行
                # 这个回调通常是通过Qt的信号槽机制连接的，
                # 它会自动处理跨线程调用
                self.progress_callback(message, percent)
            except Exception as e:
                logger.error(f"调用进度回调时出错: {str(e)}")
        
        logger.info(f"进度 {percent:.1f}%: {message}")
    
    def _start_progress_timer(self):
        """启动定期进度更新定时器，防止批处理模式中的超时检测"""
        if self._progress_timer is not None:
            return  # 已有定时器在运行
            
        def _timer_func():
            while not self.stop_requested:
                try:
                    # 每15秒重发一次最后的进度信息
                    if self._last_progress_message and self.progress_callback:
                        # 重新添加时间信息
                        if self.start_time > 0:
                            elapsed_time = time.time() - self.start_time
                            elapsed_str = self._format_time(elapsed_time)
                            message = f"{self._last_progress_message.split('(已用时:')[0].strip()} (已用时: {elapsed_str})"
                            self.progress_callback(message, self._last_progress_percent)
                            logger.debug(f"定时重发进度: {self._last_progress_percent:.1f}%: {message}")
                except Exception as e:
                    logger.error(f"进度定时器错误: {str(e)}")
                
                # 睡眠15秒
                time.sleep(15)
        
        # 创建并启动定时器线程
        self._progress_timer = threading.Thread(target=_timer_func, daemon=True)
        self._progress_timer.start()
        logger.info("已启动进度定时更新")
    
    def _stop_progress_timer(self):
        """停止定期进度更新定时器"""
        # 因为是守护线程，不需要显式终止
        self._progress_timer = None
    
    def process_batch(self, 
                      material_folders: List[Dict[str, Any]], 
                      output_dir: str, 
                      count: int = 1, 
                      bgm_path: str = None) -> Tuple[List[str], str]:
        """
        批量处理视频
        
        Args:
            material_folders: 素材文件夹信息列表
            output_dir: 输出目录
            count: 要生成的视频数量
            bgm_path: 背景音乐路径
            
        Returns:
            Tuple[List[str], str]: 生成的视频文件路径列表和总用时
        """
        self.stop_requested = False
        output_videos = []
        
        # 开始计时
        self.start_time = time.time()
        
        # 启动进度定时更新
        self._start_progress_timer()
        
        try:
            # 扫描素材文件夹
            self.report_progress("开始扫描素材文件夹...", 0)
            
            try:
                material_data = self._scan_material_folders(material_folders)
            except Exception as e:
                logger.error(f"扫描素材文件夹失败: {str(e)}")
                raise
            
            # 检查是否找到素材
            if not material_data:
                error_msg = "没有找到可用的素材文件"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 检查每个文件夹是否有视频
            for folder_name, data in material_data.items():
                if not data.get("videos", []):
                    logger.warning(f"场景 '{folder_name}' 中没有找到视频文件")
            
            self.report_progress("素材扫描完成，开始生成视频...", 5)
            
            # 生成多个视频
            output_videos = []
            
            # 计算每个视频的进度百分比
            progress_per_video = 90.0 / count if count > 0 else 0
            
            # 添加当前时间戳到文件名，避免覆盖之前的文件
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # 生成视频文件
            for i in range(count):
                if self.stop_requested:
                    logger.info("收到停止请求，中断视频批量处理")
                    break
                
                # 构建输出文件路径
                output_filename = f"合成视频_{timestamp}_{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)
                
                # 设置该视频的进度范围
                progress_start = 5 + i * progress_per_video
                progress_end = 5 + (i + 1) * progress_per_video
                
                self.report_progress(f"正在生成第 {i+1}/{count} 个视频...", progress_start)
                
                try:
                    # 处理单个视频
                    result_path = self._process_single_video(
                        material_data, 
                        output_path, 
                        bgm_path,
                        progress_start,
                        progress_end
                    )
                    
                    output_videos.append(result_path)
                    logger.info(f"第 {i+1}/{count} 个视频生成完成: {result_path}")
                except Exception as e:
                    logger.error(f"生成第 {i+1}/{count} 个视频时出错: {str(e)}")
                    # 继续处理下一个视频
                    continue
            
            # 计算总用时
            total_time = time.time() - self.start_time
            total_time_str = self._format_time(total_time)
            
            self.report_progress(f"批量视频处理完成，成功生成: {len(output_videos)}/{count}，总用时: {total_time_str}", 100)
            logger.info(f"批量视频处理完成，成功生成: {len(output_videos)}/{count}，总用时: {total_time_str}")
            
            return output_videos, total_time_str
        finally:
            # 停止进度定时更新
            self._stop_progress_timer()
    
    def stop_processing(self):
        """停止处理"""
        self.stop_requested = True
        logger.info("已请求停止视频处理")
    
    def _scan_material_folders(self, material_folders: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        扫描素材文件夹，获取视频和配音文件
        
        支持三种导入模式：
        1. 直接导入独立场景文件夹（原有模式）
        2. 导入父文件夹，从中提取按顺序排列的子文件夹作为场景（新模式）
        3. 混合模式：支持同一父文件夹下同时包含普通子文件夹和快捷方式子文件夹
        
        快捷方式支持：
        - 支持Windows快捷方式(.lnk文件)作为子文件夹
        - 自动解析快捷方式指向的实际目标文件夹
        - 支持同一父文件夹下混合普通文件夹和快捷方式
        
        Args:
            material_folders: 素材文件夹信息列表，每个字典中可以包含 extract_mode 字段指定抽取模式
            
        Returns:
            Dict[str, Dict[str, Any]]: 素材数据，按子文件夹顺序排列
        """
        # 导入解析快捷方式的函数
        from src.utils.file_utils import resolve_shortcut
        
        material_data = {}
        
        # 计算每个文件夹的扫描进度
        progress_per_folder = 4.0 / len(material_folders) if material_folders else 0
        
        for idx, folder_info in enumerate(material_folders):
            folder_path = folder_info["path"]
            folder_name = os.path.basename(folder_path)
            
            # 获取抽取模式设置，默认为单视频模式
            extract_mode = folder_info.get("extract_mode", "single_video")
            logger.info(f"文件夹 '{folder_name}' 使用抽取模式: {extract_mode}")
            
            self.report_progress(f"正在扫描素材文件夹: {folder_name}", 1 + progress_per_folder * idx)
            
            # 检测是否为父文件夹导入模式（检查是否包含子文件夹）
            is_parent_folder = False
            sub_folders = []
            normal_count = 0
            shortcut_count = 0
            shortcut_errors = 0
            
            try:
                # 获取子文件夹列表
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    
                    actual_path = item_path
                    is_shortcut = False
                    
                    # 检查是否是快捷方式
                    if item.lower().endswith('.lnk'):
                        logger.info(f"父文件夹模式：检测到可能的快捷方式: {item_path}")
                        shortcut_target = resolve_shortcut(item_path)
                        if shortcut_target:
                            actual_path = shortcut_target
                            is_shortcut = True
                            shortcut_count += 1
                            logger.info(f"检测到快捷方式子文件夹: {item_path} -> {actual_path}")
                        else:
                            shortcut_errors += 1
                            logger.warning(f"无法解析快捷方式: {item_path}")
                            continue
                    elif os.path.isdir(item_path):
                        normal_count += 1
                    else:
                        logger.debug(f"跳过非文件夹项目: {item_path}")
                        continue
                    
                    # 检查实际路径是否是目录
                    if not os.path.isdir(actual_path):
                        logger.warning(f"路径不是目录，跳过: {actual_path}")
                        continue
                    
                    # 检查子文件夹是否包含标准结构（视频文件夹或配音文件夹）
                    video_dir = os.path.join(actual_path, "视频")
                    audio_dir = os.path.join(actual_path, "配音")
                    
                    has_valid_structure = False
                    
                    if os.path.isdir(video_dir):
                        has_valid_structure = True
                    
                    if os.path.isdir(audio_dir):
                        has_valid_structure = True
                    
                    if has_valid_structure:
                        sub_folder_info = {
                            "path": actual_path,
                            "name": item,  # 保留原始名称，用于显示
                            "is_shortcut": is_shortcut,
                            "original_path": item_path if is_shortcut else None,
                            "extract_mode": extract_mode  # 传递父文件夹的抽取模式给子文件夹
                        }
                        sub_folders.append(sub_folder_info)
                    else:
                        logger.warning(f"子文件夹不包含视频或配音目录，跳过: {actual_path}")
            except Exception as e:
                logger.error(f"扫描父文件夹时出错: {folder_path}, 错误: {str(e)}")
                # 继续处理其他文件夹
            
            # 如果找到符合条件的子文件夹，认为是父文件夹导入模式
            if sub_folders:
                is_parent_folder = True
                
                # 记录混合情况的信息
                folder_detail = ""
                if normal_count > 0 and shortcut_count > 0:
                    folder_detail = f"(包含 {normal_count} 个普通子文件夹和 {shortcut_count} 个快捷方式子文件夹)"
                    logger.info(f"检测到混合模式：父文件夹 '{folder_name}' 中包含 {normal_count} 个普通子文件夹和 {shortcut_count} 个快捷方式子文件夹")
                elif shortcut_count > 0:
                    folder_detail = f"(包含 {shortcut_count} 个快捷方式子文件夹)"
                    logger.info(f"检测到纯快捷方式模式：父文件夹 '{folder_name}' 中包含 {shortcut_count} 个快捷方式子文件夹")
                else:
                    folder_detail = f"(包含 {normal_count} 个普通子文件夹)"
                    logger.info(f"检测到标准父文件夹模式：父文件夹 '{folder_name}' 中包含 {normal_count} 个普通子文件夹")
                
                # 显示有效子文件夹数量
                found_count = len(sub_folders)
                logger.info(f"在父文件夹 '{folder_name}' {folder_detail} 中找到 {found_count} 个有效子文件夹")
                
                # 如果有快捷方式解析错误，记录警告
                if shortcut_errors > 0:
                    logger.warning(f"父文件夹 '{folder_name}' 中有 {shortcut_errors} 个快捷方式无法解析")
                
                # 对子文件夹按名称排序，确保按正确顺序处理
                sub_folders.sort(key=lambda x: x["name"])
                
                # 逐个处理子文件夹
                for sub_idx, sub_folder_info in enumerate(sub_folders):
                    sub_path = sub_folder_info["path"]
                    sub_name = sub_folder_info["name"]
                    
                    if sub_folder_info["is_shortcut"]:
                        # 移除.lnk后缀，以便更好的显示
                        if sub_name.lower().endswith('.lnk'):
                            sub_name = sub_name[:-4]
                        sub_display_name = f"{sub_name} (快捷方式)"
                    else:
                        sub_display_name = sub_name
                    
                    self.report_progress(
                        f"扫描段落 {sub_idx+1}/{len(sub_folders)}: {sub_display_name}", 
                        1 + progress_per_folder * idx + (progress_per_folder * sub_idx / len(sub_folders))
                    )
                    
                    # 使用顺序编号作为键，确保段落按顺序排列
                    segment_key = f"{sub_idx+1:02d}_{sub_name}"
                    
                    # 获取此子文件夹的抽取模式
                    sub_extract_mode = sub_folder_info.get("extract_mode", extract_mode)
                    
                    # 初始化段落数据
                    material_data[segment_key] = {
                        "videos": [],
                        "audios": [],
                        "path": sub_path,
                        "segment_index": sub_idx,  # 存储段落索引，用于排序
                        "parent_folder": folder_name,  # 记录所属父文件夹
                        "is_shortcut": sub_folder_info["is_shortcut"],  # 记录是否为快捷方式
                        "original_path": sub_folder_info["original_path"],  # 记录原始快捷方式路径
                        "display_name": sub_display_name,  # 用于显示的名称
                        "extract_mode": sub_extract_mode  # 保存抽取模式设置
                    }
                    
                    try:
                        # 扫描视频文件夹
                        self._scan_media_folder(sub_path, segment_key, material_data)
                    except Exception as e:
                        logger.error(f"扫描子文件夹时出错: {sub_path}, 错误: {str(e)}")
                        # 继续处理其他子文件夹
            else:
                # 原始模式：直接扫描所提供的文件夹
                # 初始化素材数据
                material_data[folder_name] = {
                    "videos": [],
                    "audios": [],
                    "path": folder_path,
                    "display_name": folder_name,
                    "extract_mode": extract_mode  # 添加抽取模式设置
                }
                
                try:
                    # 扫描视频文件夹
                    self._scan_media_folder(folder_path, folder_name, material_data)
                except Exception as e:
                    logger.error(f"扫描素材文件夹时出错: {folder_path}, 错误: {str(e)}")
                    # 继续处理其他文件夹
        
        return material_data
    
    def _scan_media_folder(self, folder_path: str, folder_key: str, material_data: Dict[str, Dict[str, Any]]):
        """
        扫描指定文件夹的媒体文件
        
        Args:
            folder_path: 文件夹路径
            folder_key: 素材数据字典中的键
            material_data: 素材数据字典
        """
        # 查找视频文件夹
        video_folder = os.path.join(folder_path, "视频")
        if os.path.exists(video_folder) and os.path.isdir(video_folder):
            # 获取所有视频文件
            video_files = []
            for root, _, files in os.walk(video_folder):
                for file in files:
                    if file.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".wmv")):
                        video_files.append(os.path.join(root, file))
            
            # 分析视频时长
            video_info_list = []
            for video_file in video_files:
                try:
                    # 使用OpenCV获取视频信息
                    cap = cv2.VideoCapture(video_file)
                    if not cap.isOpened():
                        logger.warning(f"无法打开视频: {video_file}")
                        continue
                    
                    # 获取视频帧率和总帧数
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    # 计算视频时长(秒)
                    duration = frame_count / fps if fps > 0 else 0
                    
                    # 获取分辨率
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    cap.release()
                    
                    if duration > 0:
                        video_info = {
                            "path": video_file,
                            "duration": duration,
                            "fps": fps,
                            "width": width,
                            "height": height
                        }
                        video_info_list.append(video_info)
                except Exception as e:
                    logger.warning(f"分析视频失败: {video_file}, 错误: {str(e)}")
            
            material_data[folder_key]["videos"] = video_info_list
            logger.info(f"文件夹 '{folder_key}' 中找到 {len(video_info_list)} 个视频")
        else:
            logger.warning(f"文件夹 '{folder_key}' 中找不到视频文件夹")
        
        # 查找配音文件夹
        audio_folder = os.path.join(folder_path, "配音")
        if os.path.exists(audio_folder) and os.path.isdir(audio_folder):
            # 获取所有音频文件
            audio_files = []
            for root, _, files in os.walk(audio_folder):
                for file in files:
                    if file.lower().endswith((".mp3", ".wav", ".aac", ".ogg", ".flac")):
                        audio_files.append(os.path.join(root, file))
            
            # 分析音频时长
            audio_info_list = []
            for audio_file in audio_files:
                try:
                    # 使用MoviePy获取音频信息
                    audio_clip = AudioFileClip(audio_file)
                    duration = audio_clip.duration
                    audio_clip.close()
                    
                    if duration > 0:
                        audio_info = {
                            "path": audio_file,
                            "duration": duration
                        }
                        audio_info_list.append(audio_info)
                except Exception as e:
                    logger.warning(f"分析音频失败: {audio_file}, 错误: {str(e)}")
            
            material_data[folder_key]["audios"] = audio_info_list
            logger.info(f"文件夹 '{folder_key}' 中找到 {len(audio_info_list)} 个配音")
        else:
            logger.warning(f"文件夹 '{folder_key}' 中找不到配音文件夹")
    
    def _process_single_video(self, 
                              material_data: Dict[str, Dict[str, Any]], 
                              output_path: str, 
                              bgm_path: str = None,
                              progress_start: float = 0,
                              progress_end: float = 100) -> str:
        """
        处理单个视频
        
        Args:
            material_data: 素材数据
            output_path: 输出路径
            bgm_path: 背景音乐路径
            progress_start: 进度起始值
            progress_end: 进度结束值
        
        Returns:
            str: 输出视频路径
        """
        # 启动进度定时更新
        self._start_progress_timer()
        
        try:
            # 设置进度范围
            progress_range = progress_end - progress_start
            
            # 处理output_path，确保使用短路径名
            original_output_path = output_path
            if os.name == 'nt':
                try:
                    import win32api
                    # 确保输出目录存在
                    output_dir = os.path.dirname(output_path)
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    # 获取输出目录的短路径名
                    output_dir_short = win32api.GetShortPathName(output_dir)
                    # 合成新的输出路径
                    output_filename = os.path.basename(output_path)
                    output_path = os.path.join(output_dir_short, output_filename)
                    logger.info(f"输出路径已转换为短路径: {original_output_path} -> {output_path}")
                except ImportError:
                    logger.warning("win32api模块未安装，无法转换输出路径为短路径名")
                except Exception as e:
                    logger.warning(f"转换输出路径失败: {str(e)}，将使用原始路径")
                    output_path = original_output_path
            
            # 保持段落顺序
            # 检查是否有段落索引，如果有则按段落索引排序
            folders = []
            has_segment_structure = False
            
            for key, data in material_data.items():
                if "segment_index" in data:
                    has_segment_structure = True
                    break
            
            if has_segment_structure:
                # 按段落索引排序
                folders = sorted(material_data.keys(), 
                                key=lambda k: material_data[k].get("segment_index", 0))
                logger.info("检测到分段结构，将按段落顺序处理视频")
            else:
                # 使用原始顺序
                folders = list(material_data.keys())
            
            # 确保至少有1个场景
            if len(folders) == 0:
                error_msg = "没有可用的场景，无法生成视频"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 使用所有场景，保持原始顺序
            selected_folders = folders
            
            logger.info(f"将按顺序使用 {len(selected_folders)} 个场景: {', '.join(selected_folders)}")
            
            # 收集所选场景的素材
            self.report_progress(f"正在按顺序合成 {len(selected_folders)} 个场景...", 
                               progress_start + progress_range * 0.05)
            
            selected_clips = []
            open_resources = []  # 跟踪需要关闭的资源
            used_videos = set()  # 跟踪已使用的视频，避免重复
            
            try:
                for i, folder_name in enumerate(selected_folders):
                    if self.stop_requested:
                        logger.info("收到停止请求，中断视频合成")
                        raise InterruptedError("视频处理被用户中断")
                        
                    folder_data = material_data[folder_name]
                    
                    self.report_progress(f"处理场景: {folder_name}", 
                                       progress_start + progress_range * 0.1 + i * (progress_range * 0.4 / len(selected_folders)))
                    
                    logger.info(f"处理场景: {folder_name}")
                    videos = folder_data["videos"]
                    audios = folder_data["audios"]
                    
                    # 获取该文件夹的抽取模式，默认为"single_video"（单视频模式）
                    extract_mode = folder_data.get("extract_mode", "single_video")
                    logger.info(f"场景 '{folder_name}' 使用抽取模式: {extract_mode}")
                    
                    if not videos:
                        logger.warning(f"场景 '{folder_name}' 没有可用视频，跳过")
                        continue
                    
                    if not audios:
                        logger.warning(f"场景 '{folder_name}' 没有可用配音，使用无声视频")
                        audio_file = None
                        audio_duration = 0
                    else:
                        # 选择第一个配音
                        audio_info = audios[0]
                        audio_file = audio_info["path"]
                        audio_duration = audio_info["duration"]
                        logger.info(f"选择配音: {os.path.basename(audio_file)}, 时长: {audio_duration:.2f}秒")
                    
                    # 根据抽取模式选择不同的处理逻辑
                    if extract_mode == "multi_video" and audio_duration > 0:
                        # 多视频拼接模式
                        logger.info(f"场景 '{folder_name}' 使用多视频拼接模式")
                        
                        # 将视频按时长从长到短排序，但排除已使用的视频
                        unused_videos = [v for v in videos if v["path"] not in used_videos]
                        
                        if not unused_videos:
                            logger.warning(f"场景 '{folder_name}' 没有未使用的视频，将使用已使用过的视频")
                            unused_videos = videos
                        
                        # 按时长排序视频
                        sorted_videos = sorted(unused_videos, key=lambda v: v["duration"], reverse=True)
                        
                        # 准备拼接的片段
                        concat_clips = []
                        total_duration = 0
                        used_video_paths = []
                        
                        # 尝试拼接视频片段直到达到配音时长
                        for video_info in sorted_videos:
                            if total_duration >= audio_duration:
                                break
                                
                            video_file = video_info["path"]
                            video_duration = video_info["duration"]
                            
                            try:
                                # 加载视频剪辑
                                video_clip = VideoFileClip(video_file)
                                open_resources.append(video_clip)
                                
                                # 计算需要的时长
                                remaining_duration = audio_duration - total_duration
                                clip_duration = min(remaining_duration, video_duration)
                                
                                # 裁剪视频片段
                                if clip_duration < video_duration:
                                    video_clip = video_clip.subclip(0, clip_duration)
                                
                                # 添加到拼接列表
                                concat_clips.append(video_clip)
                                total_duration += clip_duration
                                used_video_paths.append(video_file)
                                used_videos.add(video_file)
                                
                                logger.info(f"添加视频片段: {os.path.basename(video_file)}, 时长: {clip_duration:.2f}秒, 累计时长: {total_duration:.2f}秒")
                            except Exception as e:
                                logger.error(f"加载视频 {video_file} 失败: {str(e)}")
                                # 继续尝试其他视频
                        
                        # 检查是否有足够的视频片段
                        if not concat_clips:
                            logger.warning(f"场景 '{folder_name}' 无法加载任何视频片段，跳过")
                            continue
                        
                        # 拼接视频片段
                        try:
                            if len(concat_clips) > 1:
                                video_clip = concatenate_videoclips(concat_clips)
                                logger.info(f"成功拼接 {len(concat_clips)} 个视频片段，总时长: {video_clip.duration:.2f}秒")
                            else:
                                video_clip = concat_clips[0]
                                logger.info(f"使用单个视频片段，时长: {video_clip.duration:.2f}秒")
                                
                            # 最后检查拼接后的视频时长是否满足要求
                            if video_clip.duration < audio_duration * 0.9:  # 允许10%的误差
                                logger.warning(f"拼接后视频时长 {video_clip.duration:.2f}秒 小于配音时长 {audio_duration:.2f}秒，可能会影响质量")
                            
                            # 加载配音并添加到视频
                            try:
                                audio_clip = AudioFileClip(audio_file)
                                open_resources.append(audio_clip)
                                
                                # 设置配音音量
                                audio_clip = audio_clip.volumex(self.settings["voice_volume"])
                                
                                # 将配音添加到视频
                                video_clip = video_clip.set_audio(audio_clip)
                                
                                # 将处理后的剪辑添加到列表
                                selected_clips.append({
                                    "clip": video_clip,
                                    "folder": folder_name,
                                    "video_path": ",".join(used_video_paths),  # 多个视频路径，用逗号分隔
                                    "audio_path": audio_file
                                })
                                
                                logger.info(f"场景 '{folder_name}' 多视频拼接处理完成，剪辑时长: {video_clip.duration:.2f}秒")
                            except Exception as e:
                                logger.error(f"添加配音到拼接视频失败: {str(e)}")
                                # 保持视频原声
                                selected_clips.append({
                                    "clip": video_clip,
                                    "folder": folder_name,
                                    "video_path": ",".join(used_video_paths),
                                    "audio_path": None
                                })
                        except Exception as e:
                            logger.error(f"拼接视频片段失败: {str(e)}")
                            # 跳过这个场景
                            continue
                    else:
                        # 单视频模式（原始逻辑）
                        logger.info(f"场景 '{folder_name}' 使用单视频模式")
                        
                        # 根据配音时长筛选合适的视频
                        suitable_videos = [v for v in videos if v["path"] not in used_videos and v["duration"] >= audio_duration]
                        
                        # 如果没有足够长的视频，尝试使用最长的
                        if not suitable_videos and videos:
                            suitable_videos = sorted(videos, key=lambda v: v["duration"], reverse=True)
                            if suitable_videos[0]["path"] in used_videos:
                                # 如果最长的已经使用过，尝试找其他未使用的
                                unused_videos = [v for v in videos if v["path"] not in used_videos]
                                if unused_videos:
                                    suitable_videos = sorted(unused_videos, key=lambda v: v["duration"], reverse=True)
                                else:
                                    logger.warning(f"场景 '{folder_name}' 的所有视频都已使用，将重复使用")
                                    suitable_videos = sorted(videos, key=lambda v: v["duration"], reverse=True)
                            logger.warning(f"没有找到时长大于 {audio_duration:.2f}秒 的视频，将使用最长的视频: {suitable_videos[0]['duration']:.2f}秒")
                        
                        if not suitable_videos:
                            logger.warning(f"场景 '{folder_name}' 没有合适的视频，跳过")
                            continue
                        
                        # 随机选择一个符合条件的视频，而不是总是选第一个
                        import random
                        video_info = random.choice(suitable_videos)
                        video_file = video_info["path"]
                        video_duration = video_info["duration"]
                        
                        # 记录已使用的视频
                        used_videos.add(video_file)
                        
                        logger.info(f"随机选择视频: {os.path.basename(video_file)}, 时长: {video_duration:.2f}秒")
                        
                        try:
                            # 加载视频剪辑
                            try:
                                video_clip = VideoFileClip(video_file)
                            except Exception as e:
                                logger.error(f"无法加载视频文件 {video_file}: {str(e)}")
                                logger.warning(f"跳过场景 '{folder_name}'")
                                continue
                                
                            open_resources.append(video_clip)
                            
                            # 根据配音时长裁剪视频
                            if audio_file and audio_duration > 0:
                                # 确保视频时长不小于配音时长
                                clip_duration = audio_duration
                                
                                # 如果视频比配音长，则从视频开头开始截取，而不是从中间
                                if video_duration > clip_duration:
                                    start_time = 0  # 从视频开头开始截取
                                    try:
                                        video_clip = video_clip.subclip(start_time, start_time + clip_duration)
                                        if video_clip.duration < 0.5:  # 如果裁剪后视频太短
                                            logger.warning(f"裁剪后视频时长过短: {video_clip.duration:.2f}秒，使用原始视频")
                                            video_clip = VideoFileClip(video_file)  # 重新加载原始视频
                                    except Exception as e:
                                        logger.error(f"裁剪视频时出错: {str(e)}，使用原始视频")
                                        video_clip = VideoFileClip(video_file)  # 使用原始视频
                                
                                # 加载配音
                                try:
                                    audio_clip = AudioFileClip(audio_file)
                                except Exception as e:
                                    logger.error(f"无法加载音频文件 {audio_file}: {str(e)}")
                                    logger.warning("将使用视频原声")
                                    # 保持视频原声
                                    selected_clips.append({
                                        "clip": video_clip,
                                        "folder": folder_name,
                                        "video_path": video_file,
                                        "audio_path": None
                                    })
                                    continue
                                    
                                open_resources.append(audio_clip)
                                
                                # 设置配音音量
                                audio_clip = audio_clip.volumex(self.settings["voice_volume"])
                                
                                # 将配音添加到视频
                                video_clip = video_clip.set_audio(audio_clip)
                            
                            # 将处理后的剪辑添加到列表
                            selected_clips.append({
                                "clip": video_clip,
                                "folder": folder_name,
                                "video_path": video_file,
                                "audio_path": audio_file
                            })
                            
                            logger.info(f"场景 '{folder_name}' 处理完成，剪辑时长: {video_clip.duration:.2f}秒")
                        except Exception as e:
                            logger.error(f"处理场景 '{folder_name}' 失败: {str(e)}")
                            # 继续处理其他场景，不中断整个过程
                    
                    # 添加更多进度更新点，避免长时间无更新
                    current_progress = (i + 1) / len(folders) * 0.4  # 场景选择占总进度的40%
                    self.report_progress(f"已处理 {i+1}/{len(folders)} 个场景", 
                                      progress_start + progress_range * current_progress)
                
                # 检查是否有足够的剪辑
                if len(selected_clips) < len(folders):
                    error_msg = f"没有足够的有效素材，至少需要 {len(folders)} 个场景，但只有 {len(selected_clips)} 个场景有效"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # 合并剪辑，添加转场
                self.report_progress("正在合并剪辑和添加转场效果...", 
                                   progress_start + progress_range * 0.5)
                
                try:
                    final_clip = self._merge_clips_with_transitions(selected_clips)
                    open_resources.append(final_clip)
                except Exception as e:
                    error_msg = f"合并剪辑失败: {str(e)}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                # 添加背景音乐（如果有）
                if bgm_path and os.path.exists(bgm_path):
                    self.report_progress("正在添加背景音乐...", progress_start + progress_range * 0.7)
                    
                    try:
                        # 加载背景音乐
                        bgm_clip = AudioFileClip(bgm_path)
                        open_resources.append(bgm_clip)
                        
                        # 设置背景音乐音量
                        bgm_clip = bgm_clip.volumex(self.settings["bgm_volume"])
                        
                        # 如果背景音乐比视频短，则循环播放
                        if bgm_clip.duration < final_clip.duration:
                            bgm_clip = bgm_clip.fx(vfx.loop, duration=final_clip.duration)
                        
                        # 如果背景音乐比视频长，则裁剪
                        if bgm_clip.duration > final_clip.duration:
                            bgm_clip = bgm_clip.subclip(0, final_clip.duration)
                        
                        # 将背景音乐与视频音频混合
                        if final_clip.audio is not None:
                            new_audio = CompositeAudioClip([final_clip.audio, bgm_clip])
                            final_clip = final_clip.set_audio(new_audio)
                        else:
                            final_clip = final_clip.set_audio(bgm_clip)
                        
                        logger.info("背景音乐添加成功")
                    except Exception as e:
                        logger.error(f"添加背景音乐失败: {str(e)}")
                        # 继续导出，但不使用背景音乐
                
                # 设置导出参数
                export_params = {}
                
                # 设置基本编码参数
                codec = "libx264"
                audio_codec = "aac"
                
                # 根据设置配置硬件加速和编码器
                if self.settings["hardware_accel"] != "none":
                    if self.settings["hardware_accel"] == "cuda" or (
                        self.settings["hardware_accel"] == "auto" and "nvidia" in self.settings["encoder"].lower()):
                        # NVIDIA GPU加速
                        codec = "h264_nvenc"
                        logger.info("使用NVIDIA GPU加速编码视频")
                    elif self.settings["hardware_accel"] == "qsv":
                        # Intel QSV加速
                        codec = "h264_qsv"
                        logger.info("使用Intel QSV加速编码视频")
                    elif self.settings["hardware_accel"] == "amf":
                        # AMD AMF加速
                        codec = "h264_amf"
                        logger.info("使用AMD AMF加速编码视频")
                
                # 设置比特率
                if self.settings["bitrate"] > 0:
                    export_params["bitrate"] = f"{self.settings['bitrate']}k"
                
                # 设置线程数
                if self.settings["threads"] > 0:
                    export_params["threads"] = self.settings["threads"]
                
                # 导出视频
                self.report_progress("正在导出视频...", progress_start + progress_range * 0.8)
                
                try:
                    # 先尝试使用直接FFmpeg命令进行硬件加速编码
                    if self.settings["hardware_accel"] != "none" and self._should_use_direct_ffmpeg(codec):
                        # 创建临时文件路径用于原始视频
                        temp_raw_video = self._create_temp_file("temp_raw", ".mp4")
                        
                        # 根据硬件加速类型确定要使用的编码器
                        if self.settings["hardware_accel"] == "auto" or self.settings["hardware_accel"] == "force":
                            # 如果是自动或强制硬件加速，根据encoder设置确定编码器
                            encoder_setting = self.settings.get("encoder", "").lower()
                            if "nvidia" in encoder_setting or "nvenc" in encoder_setting:
                                codec = "h264_nvenc"
                            elif "intel" in encoder_setting or "qsv" in encoder_setting:
                                codec = "h264_qsv"
                            elif "amd" in encoder_setting or "amf" in encoder_setting:
                                codec = "h264_amf"
                        
                        logger.info(f"将使用FFmpeg直接编码，编码器: {codec}")
                        logger.info(f"硬件加速配置: {self.settings['hardware_accel']}")
                        logger.info(f"编码器设置: {self.settings['encoder']}")
                        
                        # 添加进度监控函数
                        export_start_time = time.time()
                        def progress_monitor():
                            """监控视频导出进度的线程函数"""
                            last_progress = 0
                            while not self.stop_requested and os.path.exists(temp_raw_video):
                                try:
                                    # 尝试预估进度
                                    elapsed_time = time.time() - export_start_time
                                    if final_clip.duration > 0:
                                        # 以实际经过时间预估进度，假设导出处理速度为实时速度的2-5倍
                                        est_progress = min(0.95, elapsed_time / (final_clip.duration * 3))
                                        if est_progress > last_progress:
                                            last_progress = est_progress
                                            percent = progress_start + progress_range * (0.8 + 0.15 * est_progress)
                                            self.report_progress(f"正在导出临时视频... {int(est_progress * 100)}%", percent)
                                except Exception as e:
                                    logger.error(f"进度监控错误: {str(e)}")
                                
                                # 每秒更新一次进度
                                time.sleep(1)
                        
                        # 启动进度监控线程
                        progress_thread = threading.Thread(target=progress_monitor)
                        progress_thread.daemon = True
                        progress_thread.start()
                        
                        try:
                            # 导出视频时也使用GPU编码
                            # 确保使用硬件加速编码器，如果兼容模式开启则使用GPU编码器，否则回退到libx264
                            temp_codec = codec if self.settings.get("compatibility_mode", True) else "libx264"
                            logger.info(f"临时文件将使用编码器: {temp_codec}")
                            
                            # 记录最终确定的硬件编码器
                            final_encoder = temp_codec
                            logger.info(f"最终确定的硬件编码器: {final_encoder}")
                            
                            # 导出视频使用GPU编码
                            final_clip.write_videofile(
                                temp_raw_video, 
                                fps=30, 
                                codec=temp_codec,  # 对临时文件也尝试使用GPU编码
                                audio_codec="aac",
                                remove_temp=True,
                                write_logfile=False,
                                preset="fast", 
                                verbose=False,
                                threads=self.settings["threads"],
                                ffmpeg_params=[
                                    "-hide_banner", "-y",
                                    "-pix_fmt", "yuv420p",  # 确保使用标准像素格式
                                    "-profile:v", "high",   # 使用高质量配置文件
                                    "-level", "4.1",        # 兼容性级别
                                    "-movflags", "+faststart" # 优化网络流式传输
                                ]
                            )
                        except Exception as e:
                            logger.warning(f"使用GPU编码器 {codec} 处理临时文件失败: {str(e)}")
                            logger.warning("回退到使用CPU编码器(libx264)处理临时文件")
                            
                            # 如果GPU编码失败，回退到CPU编码
                            final_clip.write_videofile(
                                temp_raw_video, 
                                fps=30, 
                                codec="libx264",  # 回退到CPU编码器
                                audio_codec="aac",
                                remove_temp=True,
                                write_logfile=False,
                                preset="ultrafast", 
                                verbose=False,
                                threads=self.settings["threads"],
                                ffmpeg_params=[
                                    "-hide_banner", "-y",
                                    "-pix_fmt", "yuv420p",
                                    "-profile:v", "high",
                                    "-level", "4.1",
                                    "-movflags", "+faststart"
                                ]
                            )
                        
                        # 再使用FFmpeg进行硬件加速编码
                        if os.path.exists(temp_raw_video):
                            logger.info(f"临时文件已生成，准备使用GPU加速编码器 {codec} 进行最终编码")
                            
                            # 检查临时文件有效性
                            temp_valid = self._check_video_file(temp_raw_video)
                            if not temp_valid:
                                logger.warning(f"临时文件 {temp_raw_video} 无效或损坏，尝试重新生成")
                                # 尝试简单的拷贝转换临时文件
                                try:
                                    repaired_temp = self._create_temp_file("repaired_raw", ".mp4")
                                    ffmpeg_cmd = self._get_ffmpeg_cmd()
                                    repair_cmd = [
                                        ffmpeg_cmd, 
                                        "-i", temp_raw_video,
                                        "-c", "copy",
                                        "-y",
                                        repaired_temp
                                    ]
                                    
                                    # 处理Windows中文路径
                                    if os.name == 'nt':
                                        try:
                                            import win32api
                                            if os.path.exists(temp_raw_video):
                                                repair_cmd[2] = win32api.GetShortPathName(temp_raw_video)
                                        except Exception as e:
                                            logger.warning(f"转换临时文件路径失败: {str(e)}")
                                    
                                    logger.info(f"尝试修复临时文件: {' '.join(repair_cmd)}")
                                    subprocess.run(repair_cmd, check=True)
                                    
                                    if os.path.exists(repaired_temp) and self._check_video_file(repaired_temp):
                                        logger.info("临时文件修复成功")
                                        temp_raw_video = repaired_temp
                                    else:
                                        logger.warning("临时文件修复失败")
                                except Exception as e:
                                    logger.error(f"尝试修复临时文件时出错: {str(e)}")
                            
                            # 使用FFmpeg进行最终编码
                            success = self._encode_with_ffmpeg(temp_raw_video, output_path, self.settings["hardware_accel"], codec)
                            
                            # 如果成功，并且启用了水印功能，则添加水印
                            if success and self.settings.get("watermark_enabled", False):
                                try:
                                    self.report_progress("正在添加时间戳水印...", progress_start + progress_range * 0.95)
                                    # 使用带水印的临时文件路径
                                    watermarked_output = self._create_temp_file("watermarked", ".mp4")
                                    # 添加水印到视频
                                    watermark_success = self._add_watermark_to_video(output_path, watermarked_output)
                                    
                                    if watermark_success:
                                        # 使用临时文件替换原输出文件
                                        try:
                                            os.remove(output_path)
                                        except Exception as e:
                                            logger.warning(f"删除原输出文件失败: {str(e)}")
                                            
                                        try:
                                            shutil.move(watermarked_output, output_path)
                                            logger.info("成功添加水印并替换原输出文件")
                                        except Exception as e:
                                            logger.error(f"移动水印文件失败: {str(e)}")
                                            # 如果移动失败，尝试直接复制
                                            try:
                                                shutil.copy2(watermarked_output, output_path)
                                                os.remove(watermarked_output)
                                                logger.info("使用复制方式替换原输出文件")
                                            except Exception as copy_error:
                                                logger.error(f"复制水印文件失败: {str(copy_error)}")
                                    else:
                                        logger.warning("添加水印失败，将使用无水印版本")
                                except Exception as e:
                                    logger.error(f"添加水印过程出错: {str(e)}")
                                    logger.warning("将使用无水印版本")
                            
                            # 如果成功，删除临时文件并返回
                            if success:
                                try:
                                    os.remove(temp_raw_video)
                                except Exception as e:
                                    logger.warning(f"无法删除临时文件: {str(e)}")
                                
                                # 验证输出文件
                                if self._check_video_file(output_path):
                                    logger.info(f"使用FFmpeg硬件加速导出视频成功: {output_path}")
                                    self.report_progress("视频导出完成", progress_end)
                                    return output_path
                                else:
                                    logger.error("导出的视频文件无效或损坏")
                                    if os.path.exists(output_path):
                                        try:
                                            os.remove(output_path)
                                        except Exception:
                                            pass
                                    raise RuntimeError("导出的视频文件无效或损坏")
                            else:
                                logger.warning("硬件加速失败，回退到标准编码")
                except Exception as e:
                    logger.error(f"导出视频失败: {str(e)}")
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                            logger.info(f"已删除失败的输出文件: {output_path}")
                        except Exception as remove_error:
                            logger.warning(f"无法删除失败的输出文件: {str(remove_error)}")
                    raise RuntimeError(f"导出视频失败: {str(e)}")
            except Exception as e:
                logger.error(f"执行FFmpeg命令时出错: {str(e)}")
                return False
        finally:
            # 关闭所有打开的资源
            for res in open_resources:
                try:
                    res.close()
                except Exception:
                    pass
            
            # 关闭选定片段中的所有剪辑资源
            if 'selected_clips' in locals():
                for clip_info in selected_clips:
                    try:
                        if 'clip' in clip_info and hasattr(clip_info['clip'], 'close'):
                            clip_info['clip'].close()
                    except Exception as e:
                        logger.error(f"关闭剪辑资源时出错: {str(e)}")
    
    def _merge_clips_with_transitions(self, clip_infos: List[Dict[str, Any]]) -> VideoFileClip:
        """
        合并视频片段并添加转场效果
        
        Args:
            clip_infos: 视频片段信息列表
            
        Returns:
            VideoFileClip: 合并后的视频
        """
        if not clip_infos:
            raise ValueError("没有可用的视频片段")
        
        if len(clip_infos) == 1:
            return clip_infos[0]["clip"]
        
        # 检查是否使用转场
        transition_type = self.settings["transition"]
        if transition_type == "不使用转场":
            # 直接拼接所有片段，不应用任何转场效果
            logger.info("使用快速模式：不应用转场效果")
            clips = [info["clip"] for info in clip_infos]
            return concatenate_videoclips(clips)
        
        # 准备要合并的片段
        merged_clips = []
        
        # 添加第一个片段
        merged_clips.append(clip_infos[0]["clip"])
        
        # 为每个后续片段添加转场效果
        for i in range(1, len(clip_infos)):
            prev_clip = clip_infos[i-1]["clip"]
            curr_clip = clip_infos[i]["clip"]
            
            # 获取转场类型
            if transition_type == "随机转场":
                # 随机选择转场效果
                transition_types = ["fade", "mirror_flip", "hue_shift", "zoom", "wipe", "pixelate", "slide", "blur"]
                transition_type = random.choice(transition_types)
            
            # 转场时长
            transition_duration = self.settings["transition_duration"]
            
            # 确保有足够的转场时长
            if prev_clip.duration < transition_duration * 2:
                transition_duration = min(0.5, prev_clip.duration / 2)
            if curr_clip.duration < transition_duration * 2:
                transition_duration = min(transition_duration, curr_clip.duration / 2)
            
            # 为了处理音频转场，我们需要修改音频部分
            # 1. 保存原始音频
            prev_audio = prev_clip.audio
            curr_audio = curr_clip.audio
            
            # 2. 应用视觉转场效果
            if transition_type == "fade":
                # 淡入淡出
                prev_clip = prev_clip.fadeout(transition_duration)
                curr_clip = curr_clip.fadein(transition_duration)
            elif transition_type == "mirror_flip":
                # 镜像翻转效果
                def mirror_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    if progress < 0.5:
                        # 第一个视频逐渐镜像
                        h, w = frame.shape[:2]
                        mid = int(w * (0.5 + progress))
                        mirrored = frame.copy()
                        mirrored[:, mid:] = np.fliplr(frame[:, mid:])
                        return mirrored
                    else:
                        # 第二个视频逐渐恢复正常
                        h, w = frame.shape[:2]
                        mid = int(w * (1.0 - (progress - 0.5) * 2))
                        mirrored = frame.copy()
                        mirrored[:, :mid] = np.fliplr(frame[:, :mid])
                        return mirrored
                
                prev_clip = prev_clip.fx(vfx.custom_fx, mirror_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                # 确保转场后的片段保持合适音量
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "hue_shift":
                # 色相偏移效果
                def hue_shift_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    # 将RGB转换为HSV
                    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    # 根据进度调整色相
                    shift = int(180 * progress)
                    hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + shift) % 180
                    # 将HSV转换回RGB
                    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, hue_shift_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "zoom":
                # 缩放效果
                prev_clip = prev_clip.fx(vfx.resize, lambda t: 1 + 0.1 * t / transition_duration)
                prev_clip = prev_clip.fx(vfx.fadeout, transition_duration)
                curr_clip = curr_clip.fx(vfx.resize, lambda t: 1.1 - 0.1 * t / transition_duration)
                curr_clip = curr_clip.fx(vfx.fadein, transition_duration)
            elif transition_type == "wipe":
                # 擦除效果
                def wipe_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    h, w = frame.shape[:2]
                    mask = np.zeros((h, w), dtype=np.uint8)
                    wipe_pos = int(w * progress)
                    mask[:, :wipe_pos] = 255
                    return cv2.bitwise_and(frame, frame, mask=mask)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, wipe_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "pixelate":
                # 像素化效果
                def pixelate_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    h, w = frame.shape[:2]
                    
                    # 根据进度调整像素大小
                    pixel_size = max(1, int(20 * progress))
                    
                    # 缩小并放大回原始尺寸，产生像素化效果
                    small = cv2.resize(frame, (w // pixel_size, h // pixel_size), interpolation=cv2.INTER_LINEAR)
                    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, pixelate_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "slide": 
                # 滑动效果 - 使用自定义效果
                def slide_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    h, w = frame.shape[:2]
                    
                    # 创建一个位移变换矩阵
                    offset_x = int(w * progress)
                    M = np.float32([[1, 0, -offset_x], [0, 1, 0]])
                    
                    # 应用仿射变换实现滑动效果
                    return cv2.warpAffine(frame, M, (w, h))
                
                # 使用我们自定义的slide_effect而不是不存在的slide_out
                prev_clip = prev_clip.fx(vfx.custom_fx, slide_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                # 添加音频淡出效果
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
                
                # 为当前剪辑添加淡入效果
                curr_clip = curr_clip.fadein(transition_duration)
            elif transition_type == "blur":
                # 模糊效果
                def blur_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    
                    # 计算模糊半径，确保是大于1的奇数
                    blur_size = max(3, int(30 * progress))
                    # 确保内核大小是奇数
                    if blur_size % 2 == 0:
                        blur_size += 1
                    
                    # 应用高斯模糊
                    return cv2.GaussianBlur(frame, (blur_size, blur_size), 0)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, blur_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            else:  # 默认使用淡入淡出
                # 过渡淡出效果
                prev_clip = prev_clip.fadeout(transition_duration)
                curr_clip = curr_clip.fadein(transition_duration)
            
            # 3. 应用音频转场效果
            if curr_audio and prev_audio:
                # 音频交叉淡变
                prev_audio_clip = prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration)
                curr_audio_clip = curr_audio.subclip(0, transition_duration).audio_fadein(transition_duration)
                
                # 将这些音频应用到转场部分
                if transition_type not in ["fade", "zoom"]:  # 这些转场已经处理了音频
                    # 创建转场时的混合音频
                    mixed_audio = CompositeAudioClip([prev_audio_clip, curr_audio_clip])
                    prev_clip = prev_clip.set_audio(mixed_audio)
            
            # 确保音频转场的平滑衔接
            if i < len(clip_infos) - 1:  # 不是最后一个转场
                # 使用音频淡入淡出确保无缝衔接
                if curr_audio:
                    # 应用音频效果到主体部分
                    main_audio = curr_audio.subclip(transition_duration if curr_audio.duration > transition_duration else 0)
                    if main_audio.duration > transition_duration:
                        main_audio = main_audio.audio_fadeout(transition_duration)
                    curr_clip = curr_clip.set_audio(main_audio)
            
            # 替换之前的片段
            merged_clips[-1] = prev_clip
            
            # 添加当前片段
            merged_clips.append(curr_clip)
        
        # 合并所有片段
        final_clip = concatenate_videoclips(merged_clips)
        
        return final_clip
    
    def _create_temp_file(self, prefix: str, suffix: str) -> str:
        """
        创建临时文件
        
        Args:
            prefix: 文件名前缀
            suffix: 文件扩展名
            
        Returns:
            str: 临时文件路径
        """
        import uuid
        import datetime
        
        # 确保临时目录存在
        temp_dir = self.settings.get("temp_dir", os.path.join(os.path.expanduser("~"), "VideoMixTool", "temp"))
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        
        # 生成唯一文件名：前缀 + 时间戳 + UUID
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        unique_str = str(uuid.uuid4()).replace("-", "")[:8]
        filename = f"{prefix}_{timestamp}_{unique_str}{suffix}"
        
        # 完整路径
        temp_path = os.path.join(temp_dir, filename)
        
        # 在Windows环境下转换为短路径名
        if os.name == 'nt':
            try:
                import win32api
                # 确保目录存在
                if not os.path.exists(os.path.dirname(temp_path)):
                    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                # 创建一个空文件以获取短路径名
                with open(temp_path, 'w', encoding='utf-8') as f:
                    pass
                # 获取短路径名
                temp_path = win32api.GetShortPathName(temp_path)
                logger.debug(f"临时文件路径已转换为短路径: {temp_path}")
            except ImportError:
                logger.warning("win32api模块未安装，无法转换为短路径名")
            except Exception as e:
                logger.warning(f"转换临时文件路径失败: {str(e)}")
        
        logger.debug(f"创建临时文件: {temp_path}")
        return temp_path
    
    def clean_temp_files(self):
        """清理临时文件"""
        temp_dir = self.settings["temp_dir"]
        
        if os.path.exists(temp_dir):
            try:
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                
                logger.info("临时文件清理完成")
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}") 
    
    def _should_use_direct_ffmpeg(self, codec):
        """
        判断是否应该使用直接FFmpeg命令进行编码
        主要用于启用硬件加速时跳过MoviePy的编码流程
        
        关于重编码模式和快速不重编码模式：
        
        1. 重编码模式（返回False）：
           - 使用MoviePy处理视频后再使用FFmpeg编码
           - 优势：
             * 更高的兼容性和稳定性
             * 支持更丰富的视频处理效果
             * 更适合复杂的视频特效和转场
           - 劣势：
             * 处理速度较慢，需要两次编码
             * 可能导致额外的质量损失
             * 内存占用较高
           
        2. 快速不重编码模式（返回True）：
           - 直接使用FFmpeg硬件加速编码，跳过MoviePy的编码流程
           - 优势：
             * 处理速度更快，通常快2-5倍
             * 减少视频质量损失
             * 更高效利用GPU资源
             * 内存占用更低
           - 劣势：
             * 可能与某些特效或转场不兼容
             * 在旧GPU或驱动上可能不稳定
             * 编码选项较为有限
        
        Args:
            codec: 当前使用的编码器
            
        Returns:
            bool: 是否应该使用直接FFmpeg命令
        """
        # 优先检查视频模式设置
        video_mode = self.settings.get("video_mode", "")
        if video_mode == "standard_mode":
            logger.info("使用标准模式(重编码)，不使用直接FFmpeg")
            return False
        elif video_mode == "fast_mode":
            logger.info("使用快速模式(不重编码)，将使用直接FFmpeg")
            return True
        
        # 如果没有指定视频模式或使用旧的设置格式，则使用原有逻辑
        
        # 如果硬件加速没有启用，直接返回False
        hardware_accel = self.settings.get("hardware_accel", "none")
        if hardware_accel == "none":
            logger.info(f"硬件加速未启用，不使用直接FFmpeg")
            return False
        
        # 检查编码器
        # 根据硬件加速设置调整编码器
        encoder_setting = self.settings.get("encoder", "").lower()
        if hardware_accel != "none":
            if "nvidia" in encoder_setting or "nvenc" in encoder_setting:
                codec = "h264_nvenc"
            elif "intel" in encoder_setting or "qsv" in encoder_setting:
                codec = "h264_qsv"
            elif "amd" in encoder_setting or "amf" in encoder_setting:
                codec = "h264_amf"
            elif codec == "libx264":  # 如果是CPU编码器但启用了硬件加速
                # 尝试自动检测硬件类型
                try:
                    from hardware.gpu_config import GPUConfig
                    gpu_config = GPUConfig()
                    if gpu_config.is_hardware_acceleration_enabled():
                        encoder = gpu_config.get_encoder()
                        if encoder and encoder != "libx264":
                            codec = encoder
                            logger.info(f"从GPU配置中获取编码器: {codec}")
                except Exception as e:
                    logger.warning(f"检查GPU配置时出错: {str(e)}")
                    # 默认使用NVENC
                    codec = "h264_nvenc"
                    logger.info(f"无法确定硬件编码器，默认使用: {codec}")
        
        # 只对特定的硬件加速编码器使用直接FFmpeg命令
        hw_encoders = ["h264_nvenc", "h264_qsv", "h264_amf", "hevc_nvenc", "hevc_qsv", "hevc_amf"]
        result = codec in hw_encoders
        logger.info(f"编码器 {codec} {'支持' if result else '不支持'}直接FFmpeg硬件加速")
        return result
    
    def _encode_with_ffmpeg(self, input_path, output_path, hardware_type="auto", codec="libx264"):
        """
        使用FFmpeg进行视频编码
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            hardware_type: 硬件加速类型
            codec: 视频编码器
            
        Returns:
            bool: 编码是否成功
        """
        # 添加进度更新定时器，防止批处理模式中的超时检测
        export_start_time = time.time()
        self._encoding_completed = False
        
        def progress_update_timer():
            """定期发送进度更新的线程函数，防止超时检测"""
            while not self.stop_requested and not hasattr(self, '_encoding_completed'):
                try:
                    # 计算已用时间，估算进度
                    elapsed_time = time.time() - export_start_time
                    self.report_progress(f"视频编码中... (已用时: {self._format_time(elapsed_time)})", 85)
                except Exception as e:
                    logger.error(f"进度更新定时器错误: {str(e)}")
                # 每15秒更新一次进度
                time.sleep(15)
        
        # 启动进度更新定时器
        progress_thread = threading.Thread(target=progress_update_timer)
        progress_thread.daemon = True
        progress_thread.start()
        
        try:
            # 获取FFmpeg命令路径
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 记录原始编码器
            original_codec = codec
            
            # 检查是否启用了硬件加速
            if hardware_type != "none" and hardware_type != "":
                # 如果指定了硬件加速但编码器为默认编码器，则根据硬件类型选择合适的编码器
                if codec == "libx264":
                    # 尝试从encoder设置中确定正确的硬件编码器
                    encoder_setting = self.settings.get("encoder", "").lower()
                    if "nvenc" in encoder_setting:
                        codec = "h264_nvenc"
                        logger.info(f"根据encoder设置调整为NVIDIA编码器: {codec}")
                    elif "qsv" in encoder_setting:
                        codec = "h264_qsv"
                        logger.info(f"根据encoder设置调整为Intel编码器: {codec}")
                    elif "amf" in encoder_setting:
                        codec = "h264_amf"
                        logger.info(f"根据encoder设置调整为AMD编码器: {codec}")
                    else:
                        # 如果无法从encoder设置确定，根据硬件类型推断
                        if hardware_type == "auto" or "nvidia" in hardware_type:
                            codec = "h264_nvenc"
                            logger.info(f"根据硬件加速类型调整为NVIDIA编码器: {codec}")
                        elif "intel" in hardware_type:
                            codec = "h264_qsv"
                            logger.info(f"根据硬件加速类型调整为Intel编码器: {codec}")
                        elif "amd" in hardware_type:
                            codec = "h264_amf"
                            logger.info(f"根据硬件加速类型调整为AMD编码器: {codec}")
            
            # 记录最终确定的硬件编码器
            logger.info(f"最终确定的编码器: {codec} (原始编码器: {original_codec})")
            
            # 检查是否启用了兼容模式
            compatibility_mode = True  # 默认启用兼容模式
            gpu_config = None
            try:
                # 尝试从配置中读取兼容模式设置
                from hardware.gpu_config import GPUConfig
                gpu_config = GPUConfig()
                compatibility_mode = gpu_config.is_compatibility_mode_enabled()
                logger.info(f"GPU兼容模式设置: {'启用' if compatibility_mode else '禁用'}")
            except Exception as e:
                logger.warning(f"读取GPU兼容模式设置时出错: {str(e)}，将使用默认兼容模式")
            
            # 视频格式标准化参数 - 添加这些参数确保输出视频兼容性
            format_params = [
                "-pix_fmt", "yuv420p",   # 使用标准像素格式
                "-profile:v", "high",    # 使用高质量配置文件
                "-level", "4.1",         # 兼容性级别
                "-movflags", "+faststart", # 优化网络流式传输
                "-g", "30",              # 设定关键帧间隔，提高转场质量
                "-keyint_min", "15",     # 最小关键帧间隔，确保转场区域有足够关键帧
                "-sc_threshold", "40"    # 场景切换阈值，提高转场处理效果
            ]
            
            # GPU加速相关参数
            gpu_params = []
            # NVENC特殊参数
            if "nvenc" in codec:
                # 使用兼容模式参数还是高性能参数
                if compatibility_mode:
                    logger.info("使用NVENC编码 - 兼容模式参数")
                    gpu_params = [
                        "-c:v", codec,
                        "-preset", "p4",  # 兼容性好的预设
                        "-b:v", f"{self.settings['bitrate']}k",
                        "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k", # 增大最大比特率，提高转场质量
                        "-bufsize", f"{self.settings['bitrate'] * 3}k",        # 增大缓冲区大小，优化转场处理
                        "-spatial-aq", "1",  # 保留基础的自适应量化
                        "-temporal-aq", "1", # 保留基础的时间自适应量化
                        "-rc-lookahead", "32", # 增加前瞻帧数，提高转场区域的处理质量
                        "-b_ref_mode", "middle" # 改进B帧参考模式
                    ]
                else:
                    logger.info("使用NVENC编码 - 高性能模式参数")
                    # 新版NVENC参数格式
                    gpu_params = [
                        "-c:v", codec,
                        "-preset", "p2",
                        "-tune", "hq",
                        "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                        "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 增大最大比特率
                        "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k", # 增大缓冲区
                        "-rc", "vbr",  # 使用vbr替代vbr_hq
                        "-multipass", "2",  # 添加多通道编码参数
                        "-spatial-aq", "1",
                        "-temporal-aq", "1",
                        "-cq", "19",
                        "-rc-lookahead", "32", # 增加前瞻帧数
                        "-b_ref_mode", "middle" # 改进B帧参考模式
                    ]
            # QSV特殊参数
            elif codec == "h264_qsv":
                gpu_params = [
                    "-c:v", codec,
                    "-preset", "medium",
                    "-global_quality", "21", # 降低数值，提高质量
                    "-b:v", f"{self.settings['bitrate']}k",
                    "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k", # 提高最大比特率
                    "-look_ahead", "1", # 开启前瞻，提高转场质量
                    "-adaptive_i", "1", # 自适应I帧，有助于场景切换
                    "-adaptive_b", "1"  # 自适应B帧，提高压缩效率
                ]
            # AMF特殊参数
            elif codec == "h264_amf":
                gpu_params = [
                    "-c:v", codec,
                    "-quality", "quality",
                    "-usage", "transcoding",
                    "-b:v", f"{self.settings['bitrate']}k",
                    "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k", # 提高最大比特率
                    "-header_insertion", "1", # 优化转场处的包头
                    "-bf", "4", # 增加B帧数量，提高压缩率和转场处理
                    "-preanalysis", "1" # 预分析模式，提高转场质量
                ]
            else:
                # 其他编码器使用基本参数 (如libx264)
                gpu_params = [
                    "-c:v", codec,
                    "-preset", "medium",  # libx264的预设
                    "-crf", "22",         # 降低crf值，提高质量以减少转场处的方块
                    "-b:v", f"{self.settings['bitrate']}k",
                    "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k",
                    "-bufsize", f"{self.settings['bitrate'] * 3}k",
                    "-b_strategy", "1",   # B帧决策策略
                    "-bf", "3",           # 最大B帧数量
                    "-refs", "4"          # 参考帧数，提高质量
                ]
            
            # 通用参数
            common_params = [
                "-i", input_path,
                "-c:a", "aac",  # 音频编码器
                "-b:a", "192k", # 音频比特率
                "-ar", "48000", # 音频采样率
                "-y"            # 覆盖输出文件
            ]
            
            # 如果指定了线程数
            thread_params = []
            if self.settings["threads"] > 0:
                thread_params = ["-threads", str(self.settings["threads"])]
            
            # 组合完整命令
            cmd = [ffmpeg_cmd] + common_params + gpu_params + format_params + thread_params + [output_path]
            
            # 记录实际使用的命令
            cmd_str = " ".join(cmd)
            logger.info(f"执行FFmpeg硬件加速编码: {cmd_str}")
            
            # 执行命令
            try:
                # 创建一个临时文件来捕获输出
                log_file = self._create_temp_file("ffmpeg_log", ".txt")
                
                # 在开始编码前记录GPU状态
                if codec == "h264_nvenc":
                    self._log_gpu_info("编码开始前")
                
                # 确保命令中的路径符合Windows命令行要求（处理中文路径）
                # 将cmd中的所有路径参数进行正确转换
                # 路径可能出现在input_path，output_path参数位置
                if os.name == 'nt':  # 在Windows系统下
                    for i, arg in enumerate(cmd):
                        # 如果参数看起来像文件路径（包含路径分隔符）
                        if isinstance(arg, str) and ('/' in arg or '\\' in arg):
                            # 使用短路径名来避免中文路径问题
                            try:
                                import win32api
                                # 确保路径存在，如果是输出路径可能还不存在
                                if os.path.exists(arg) or i == len(cmd) - 1:  # 最后一个参数是输出路径
                                    # 如果是输出路径但目录不存在，则先创建目录
                                    if i == len(cmd) - 1 and not os.path.exists(os.path.dirname(arg)):
                                        os.makedirs(os.path.dirname(arg), exist_ok=True)
                                    # 获取短路径名
                                    if os.path.exists(arg):
                                        cmd[i] = win32api.GetShortPathName(arg)
                                        logger.debug(f"将路径转换为短路径: {arg} -> {cmd[i]}")
                            except Exception as e:
                                logger.warning(f"转换路径时出错: {str(e)}，将保持原始路径")
                
                with open(log_file, 'w', encoding='utf-8') as log:
                    # 设置编码为UTF-8并启用错误替换
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        text=True,
                        encoding='utf-8',      # 明确设置编码为UTF-8
                        errors='replace',       # 对于无法解码的字符进行替换
                        shell=False            # 避免shell注入风险
                    )
                    
                    # 记录开始时间
                    start_time = time.time()
                    frames_processed = 0
                    
                    # 实时读取输出并写入日志
                    for line in process.stdout:
                        log.write(line)
                        log.flush()
                        
                        # 解析进度信息并更新UI
                        if "frame=" in line and "fps=" in line:
                            try:
                                frame_match = re.search(r'frame=\s*(\d+)', line)
                                fps_match = re.search(r'fps=\s*(\d+)', line)
                                
                                if frame_match and fps_match:
                                    frames_processed = int(frame_match.group(1))
                                    current_fps = int(fps_match.group(1))
                                    
                                    elapsed = time.time() - start_time
                                    if elapsed > 0 and frames_processed > 0:
                                        self.report_progress(
                                            f"正在使用GPU加速编码... {frames_processed}帧 @ {current_fps} fps", 
                                            90 + min(9, (elapsed / 60) * 9)  # 进度估算，最多到99%
                                        )
                                        
                                        # 每处理500帧记录一次GPU状态
                                        if frames_processed % 500 == 0 and codec == "h264_nvenc":
                                            self._log_gpu_info(f"处理中 ({frames_processed}帧)")
                            except Exception as e:
                                logger.debug(f"解析FFmpeg输出时出错: {str(e)}")
                        
                        # 如果用户请求停止处理，中断进程
                        if self.stop_requested:
                            process.terminate()
                            logger.info("FFmpeg编码过程被用户中断")
                            return False
                    
                    # 等待进程完成
                    process.wait()
                    
                    # 记录编码完成后的GPU状态
                    if codec == "h264_nvenc":
                        self._log_gpu_info("编码完成后")
                    
                    # 计算编码时间和平均帧率
                    encode_time = time.time() - start_time
                    avg_fps = frames_processed / encode_time if encode_time > 0 else 0
                    
                    # 检查返回码
                    if process.returncode == 0:
                        logger.info(f"FFmpeg硬件加速编码成功，用时: {encode_time:.2f}秒，平均帧率: {avg_fps:.2f}fps")
                        logger.info(f"命令行日志保存在: {log_file}")
                        
                        # 显示输出文件信息
                        if os.path.exists(output_path):
                            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                            logger.info(f"输出文件大小: {file_size:.2f} MB")
                            
                            # 提取文件时长和比特率
                            try:
                                # 同样处理info_cmd中的路径
                                info_cmd = [ffmpeg_cmd, "-i", output_path]
                                
                                # 在Windows环境下处理可能包含中文的路径
                                if os.name == 'nt':
                                    try:
                                        import win32api
                                        if os.path.exists(output_path):
                                            info_cmd[2] = win32api.GetShortPathName(output_path)
                                    except Exception as e:
                                        logger.warning(f"转换输出路径时出错: {str(e)}，将保持原始路径")
                                
                                info_proc = subprocess.Popen(
                                    info_cmd, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True,
                                    encoding='utf-8',  # 确保使用UTF-8编码
                                    errors='replace'   # 对于无法解码的字符进行替换
                                )
                                _, stderr = info_proc.communicate()
                                
                                # 提取时长
                                duration_match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', stderr)
                                if duration_match:
                                    hours, minutes, seconds = map(float, duration_match.groups())
                                    total_seconds = hours * 3600 + minutes * 60 + seconds
                                    logger.info(f"输出视频时长: {total_seconds:.2f}秒")
                                
                                # 提取比特率
                                bitrate_match = re.search(r'bitrate: (\d+) kb/s', stderr)
                                if bitrate_match:
                                    bitrate = int(bitrate_match.group(1))
                                    logger.info(f"输出视频比特率: {bitrate} kb/s")
                            except Exception as e:
                                logger.debug(f"提取输出文件信息时出错: {str(e)}")
                        
                        return True
                    else:
                        logger.error(f"FFmpeg进程返回错误码: {process.returncode}")
                        
                        # 尝试从日志中提取错误信息
                        try:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                last_lines = "".join(f.readlines()[-20:])  # 读取最后20行
                                logger.error(f"FFmpeg错误输出: {last_lines}")
                        except Exception:
                            pass
                        
                        return False
            except Exception as e:
                logger.error(f"执行FFmpeg命令时出错: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"执行FFmpeg命令时出错: {str(e)}")
            return False
        finally:
            # 标记编码已完成，停止进度更新
            self._encoding_completed = True
            # 停止进度更新定时器（设置超时，避免阻塞）
            try:
                progress_thread.join(timeout=1.0)
            except Exception as e:
                logger.error(f"停止进度更新线程时出错: {str(e)}")
    
    def _get_ffmpeg_cmd(self):
        """
        获取FFmpeg命令路径
        
        Returns:
            str: FFmpeg可执行文件路径
        """
        ffmpeg_cmd = "ffmpeg"
        
        # 尝试从ffmpeg_path.txt读取自定义路径
        try:
            # 获取项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent
            ffmpeg_path_file = project_root / "ffmpeg_path.txt"
            
            if ffmpeg_path_file.exists():
                with open(ffmpeg_path_file, 'r', encoding="utf-8") as f:
                    custom_path = f.read().strip()
                    if custom_path and os.path.exists(custom_path):
                        logger.info(f"使用自定义FFmpeg路径: {custom_path}")
                        
                        # 在Windows环境下处理中文路径
                        if os.name == 'nt':
                            try:
                                import win32api
                                custom_path = win32api.GetShortPathName(custom_path)
                                logger.info(f"转换为短路径名: {custom_path}")
                            except ImportError:
                                logger.warning("无法导入win32api模块，将使用原始路径")
                            except Exception as e:
                                logger.warning(f"转换FFmpeg路径时出错: {str(e)}，将使用原始路径")
                        
                        ffmpeg_cmd = custom_path
        except Exception as e:
            logger.error(f"读取自定义FFmpeg路径时出错: {str(e)}")
        
        return ffmpeg_cmd

    def _log_gpu_info(self, stage=""):
        """
        记录GPU状态信息
        
        Args:
            stage: 当前阶段描述
        """
        try:
            # 基本GPU利用率
            utilization_cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory",
                               "--format=csv,noheader,nounits"]
            output = subprocess.check_output(utilization_cmd, universal_newlines=True).strip().split(', ')
            
            if len(output) >= 2:
                gpu_util = output[0]
                mem_util = output[1]
                logger.info(f"GPU状态({stage}) - 利用率: {gpu_util}%, 显存利用率: {mem_util}%")
            
            # 编码器使用情况
            encoder_cmd = ["nvidia-smi", "--query-gpu=encoder.stats.sessionCount,encoder.stats.averageFps",
                          "--format=csv,noheader,nounits"]
            encoder_output = subprocess.check_output(encoder_cmd, universal_newlines=True).strip().split(', ')
            
            if len(encoder_output) >= 2:
                session_count = encoder_output[0]
                avg_fps = encoder_output[1]
                logger.info(f"编码器状态({stage}) - 会话数: {session_count}, 平均帧率: {avg_fps} fps")
        except Exception as e:
            logger.debug(f"记录GPU信息时出错: {str(e)}") 
    
    def _check_video_file(self, file_path: str) -> bool:
        """
        检查视频文件是否有效
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            bool: 文件是否有效
        """
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 1000:
            logger.warning(f"视频文件不存在或太小: {file_path}")
            return False
            
        try:
            # 使用ffprobe检查文件有效性
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            ffprobe_cmd = ffmpeg_cmd.replace("ffmpeg", "ffprobe")
            
            # 如果ffprobe不存在，尝试使用ffmpeg
            if not os.path.exists(ffprobe_cmd):
                ffprobe_cmd = ffmpeg_cmd
                
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    if os.path.exists(file_path):
                        file_path_short = win32api.GetShortPathName(file_path)
                    else:
                        return False
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}")
                    file_path_short = file_path
            else:
                file_path_short = file_path
                
            # 构建命令
            cmd = [ffprobe_cmd, "-v", "error", "-select_streams", "v:0", "-show_entries", 
                   "stream=codec_type,width,height,duration", "-of", "json", file_path_short]
                
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                logger.warning(f"ffprobe检查视频失败: {result.stderr}")
                return False
                
            # 检查输出是否包含有效的视频流信息
            if "codec_type" in result.stdout and "video" in result.stdout:
                return True
            else:
                logger.warning(f"视频文件不包含有效视频流: {file_path}")
                return False
                
        except Exception as e:
            logger.warning(f"检查视频文件有效性时出错: {str(e)}")
            return False

    def _get_watermark_text(self) -> str:
        """
        生成时间戳水印文本
        
        Returns:
            str: 格式化的时间戳水印文本
        """
        # 获取当前时间
        now = datetime.datetime.now()
        # 格式化为 年.月日.时分
        timestamp = now.strftime("%Y.%m%d.%H%M")
        
        # 检查是否有自定义前缀
        prefix = self.settings.get("watermark_prefix", "")
        if prefix:
            return f"{prefix}{timestamp}"
        else:
            return timestamp

    def _add_watermark_to_video(self, input_path: str, output_path: str) -> bool:
        """
        向视频添加时间戳水印
        
        Args:
            input_path: 输入视频路径
            output_path: 输出带水印的视频路径
            
        Returns:
            bool: 是否成功添加水印
        """
        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            if not ffmpeg_cmd:
                logger.error("未找到FFmpeg命令，无法添加水印")
                return False
                
            # 获取水印文本
            watermark_text = self._get_watermark_text()
            
            # 检查同一分钟是否已有视频生成
            # 如果有，则在时间戳后面添加编号，例如 (1), (2) 等
            dir_path = os.path.dirname(output_path)
            base_name = os.path.basename(output_path)
            count = 0
            
            # 查找同一分钟生成的视频数量
            for file in os.listdir(dir_path):
                if file.endswith(".mp4") and watermark_text in file:
                    count += 1
            
            # 如果已经有同一分钟的视频，则添加编号
            if count > 0:
                watermark_text = f"{watermark_text}({count})"
            
            # 获取水印设置
            font_size = self.settings.get("watermark_size", 24)
            font_color = self.settings.get("watermark_color", "#FFFFFF")
            position = self.settings.get("watermark_position", "右上角")
            pos_x_offset = self.settings.get("watermark_pos_x", 0)
            pos_y_offset = self.settings.get("watermark_pos_y", 0)
            
            # 转换RGB颜色为十六进制，并去掉#前缀
            if font_color.startswith("#"):
                font_color = font_color[1:]
            
            # 获取视频分辨率
            probe_cmd = [
                ffmpeg_cmd, 
                "-i", input_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0"
            ]
            
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    if os.path.exists(input_path):
                        probe_cmd[2] = win32api.GetShortPathName(input_path)
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}")
            
            # 获取视频尺寸
            try:
                result = subprocess.check_output(probe_cmd, universal_newlines=True).strip()
                width, height = map(int, result.split('x'))
            except Exception as e:
                logger.error(f"获取视频尺寸失败: {str(e)}")
                # 默认使用1080p尺寸
                if "1080p" in self.settings.get("resolution", ""):
                    if "竖屏" in self.settings.get("resolution", ""):
                        width, height = 1080, 1920
                    else:
                        width, height = 1920, 1080
                else:
                    width, height = 1280, 720
            
            # 确定水印位置
            positions = {
                "右上角": f"x=w-tw-10{pos_x_offset:+}:y=10{pos_y_offset:+}",
                "左上角": f"x=10{pos_x_offset:+}:y=10{pos_y_offset:+}",
                "右下角": f"x=w-tw-10{pos_x_offset:+}:y=h-th-10{pos_y_offset:+}",
                "左下角": f"x=10{pos_x_offset:+}:y=h-th-10{pos_y_offset:+}",
                "中心": f"x=(w-tw)/2{pos_x_offset:+}:y=(h-th)/2{pos_y_offset:+}"
            }
            
            # 获取对应位置的坐标表达式
            position_expr = positions.get(position, positions["右上角"])
            
            # 构建FFmpeg命令
            # 使用drawtext过滤器添加水印
            drawtext_filter = f"drawtext=text='{watermark_text}':fontsize={font_size}:fontcolor=0x{font_color}:box=0:{position_expr}"
            
            # 检查是否使用快速模式和兼容模式
            is_fast_mode = self.settings.get("video_mode", "") in ["fast_mode", "ultra_fast_mode"]
            is_ultra_fast = self.settings.get("video_mode", "") == "ultra_fast_mode"
            compatibility_mode = self.settings.get("compatibility_mode", False)
            
            # 完整的FFmpeg命令
            cmd = [
                ffmpeg_cmd,
                "-i", input_path,
                "-vf", drawtext_filter
            ]
            
            # 添加优化的编码参数，减少转场处的乱码和方块
            cmd.extend([
                "-g", "30",              # 设定关键帧间隔，提高转场质量
                "-keyint_min", "15",     # 最小关键帧间隔，确保转场区域有足够关键帧
                "-sc_threshold", "40"    # 场景切换阈值，提高转场处理效果
            ])
            
            # 根据模式选择不同的编码方式
            encoder = self.settings.get("encoder", "libx264")
            
            # 对于NVENC编码器使用特殊参数
            if "nvenc" in encoder:
                # 使用与FFmpeg编码相同的优化参数
                cmd.extend([
                    "-c:v", encoder,
                    "-preset", "p2",
                    "-tune", "hq",
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 增大最大比特率
                    "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k", # 增大缓冲区
                    "-spatial-aq", "1",
                    "-temporal-aq", "1",
                    "-rc-lookahead", "32" # 增加前瞻帧数
                ])
            elif "qsv" in encoder:
                # 对于Intel QSV编码器
                cmd.extend([
                    "-c:v", encoder,
                    "-preset", "medium",
                    "-global_quality", "21", # 降低数值，提高质量
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 提高最大比特率
                    "-look_ahead", "1", # 开启前瞻，提高转场质量
                    "-adaptive_i", "1", # 自适应I帧，有助于场景切换
                    "-adaptive_b", "1"  # 自适应B帧，提高压缩效率
                ])
            elif "amf" in encoder:
                # 对于AMD AMF编码器
                cmd.extend([
                    "-c:v", encoder,
                    "-quality", "quality",
                    "-usage", "transcoding",
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 提高最大比特率
                    "-header_insertion", "1", # 优化转场处的包头
                    "-bf", "4" # 增加B帧数量，提高压缩率和转场处理
                ])
            else:
                # 对于CPU编码器
                cmd.extend([
                    "-c:v", encoder,
                    "-preset", "medium",
                    "-crf", "22",         # 降低crf值，提高质量以减少转场处的方块
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k",
                    "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k",
                    "-b_strategy", "1",   # B帧决策策略
                    "-bf", "3",           # 最大B帧数量
                    "-refs", "4"          # 参考帧数，提高质量
                ])
            
            # 设置通用格式参数
            cmd.extend([
                "-pix_fmt", "yuv420p",          # 标准像素格式
                "-profile:v", "high",           # 高质量配置文件
                "-level", "4.1",                # 兼容性级别
                "-movflags", "+faststart",      # 优化网络流式传输
                "-c:a", "copy"                  # 复制音频，不重新编码
            ])
            
            # 添加输出路径和覆盖参数
            cmd.extend([
                "-y",  # 覆盖已存在的文件
                output_path
            ])
            
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    if os.path.exists(input_path):
                        cmd[2] = win32api.GetShortPathName(input_path)
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}")
            
            # 记录命令并执行
            cmd_str = " ".join(cmd)
            logger.info(f"添加水印命令: {cmd_str}")
            
            result = subprocess.run(cmd, check=True)
            
            # 检查是否成功
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"成功添加水印: {watermark_text}")
                return True
            else:
                logger.error("添加水印过程返回非零状态")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"添加水印时FFmpeg命令执行失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"添加水印时发生错误: {str(e)}")
            return False

    def _get_video_dimensions(self, video_path):
        """获取视频的宽度和高度"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_streams',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return stream.get('width', 0), stream.get('height', 0)
            
            return 0, 0
        except Exception as e:
            self.logger.error(f"获取视频尺寸失败: {e}")
            return 0, 0

    def _check_video_file(self, video_path):
        """检查视频文件是否有效"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_streams',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return True
            
            return False
        except Exception as e:
            self.logger.warning(f"ffprobe检查视频失败: {e}")
            return False