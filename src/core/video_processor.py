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

try:
    import cv2
    import numpy as np
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx, CompositeAudioClip
except ImportError as e:
    raise ImportError(f"请安装必要的依赖: {e}")

from utils.logger import get_logger

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
            "temp_dir": Path.home() / "VideoMixTool" / "temp"  # 临时文件目录
        }
        
        # 更新设置
        self.settings = self.default_settings.copy()
        if settings:
            self.settings.update(settings)
        
        # 保存进度回调
        self.progress_callback = progress_callback
        
        # 确保临时目录存在
        os.makedirs(self.settings["temp_dir"], exist_ok=True)
        
        # 初始化随机数生成器
        random.seed(time.time())
        
        # 停止标志
        self.stop_requested = False
        
        # 检查FFmpeg是否可用
        self._check_ffmpeg()
    
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
                with open(ffmpeg_path_file, 'r') as f:
                    custom_path = f.read().strip()
                    if custom_path and os.path.exists(custom_path):
                        logger.info(f"使用自定义FFmpeg路径: {custom_path}")
                        ffmpeg_cmd = custom_path
        except Exception as e:
            logger.error(f"读取自定义FFmpeg路径时出错: {str(e)}")
        
        try:
            # 尝试执行ffmpeg命令
            result = subprocess.run(
                [ffmpeg_cmd, "-version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0:
                logger.info("FFmpeg可用，版本信息：" + result.stdout.splitlines()[0])
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
        except Exception as e:
            logger.error(f"检查FFmpeg时出错: {str(e)}, 类型: {type(e).__name__}")
            return False
    
    def report_progress(self, message: str, percent: float):
        """
        报告进度
        
        Args:
            message: 状态消息
            percent: 进度百分比 (0-100)
        """
        if self.progress_callback:
            try:
                # 进度更新应该在主线程中进行
                # 这个回调通常是通过Qt的信号槽机制连接的，
                # 它会自动处理跨线程调用
                self.progress_callback(message, percent)
            except Exception as e:
                logger.error(f"调用进度回调时出错: {str(e)}")
        
        logger.info(f"进度 {percent:.1f}%: {message}")
    
    def process_batch(self, 
                      material_folders: List[Dict[str, Any]], 
                      output_dir: str, 
                      count: int = 1, 
                      bgm_path: str = None) -> List[str]:
        """
        批量处理视频
        
        Args:
            material_folders: 素材文件夹信息列表，每个字典包含场景名称、路径等信息
            output_dir: 输出目录
            count: 生成视频数量
            bgm_path: 背景音乐路径
            
        Returns:
            List[str]: 生成的视频文件路径列表
        """
        logger.info(f"开始批量处理视频，生成数量: {count}")
        logger.info(f"素材文件夹数量: {len(material_folders)}")
        logger.info(f"输出目录: {output_dir}")
        
        if not material_folders:
            error_msg = "没有可用的素材文件夹，请先添加素材"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # 检查素材文件是否存在
        for folder_info in material_folders:
            folder_path = folder_info.get("path", "")
            if not os.path.exists(folder_path):
                error_msg = f"素材文件夹不存在: {folder_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
        
        # 检查输出目录
        if not output_dir:
            error_msg = "未指定输出目录"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # 尝试创建输出目录并检查权限
        try:
            os.makedirs(output_dir, exist_ok=True)
            # 测试写入权限
            test_file = os.path.join(output_dir, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except PermissionError:
            error_msg = f"没有写入输出目录的权限: {output_dir}"
            logger.error(error_msg)
            raise PermissionError(error_msg)
        except Exception as e:
            error_msg = f"创建或访问输出目录时出错: {output_dir}, 错误: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # 检查背景音乐
        if bgm_path and not os.path.exists(bgm_path):
            warning_msg = f"背景音乐文件不存在: {bgm_path}，将不使用背景音乐"
            logger.warning(warning_msg)
            bgm_path = None
        
        # 再次检查FFmpeg是否可用
        if not self._check_ffmpeg():
            error_msg = "FFmpeg不可用，无法执行视频处理。请安装FFmpeg并确保可以在命令行中使用，或使用配置路径功能。"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # 重置停止标志
        self.stop_requested = False
        
        # 扫描素材文件夹前检查硬件状态
        try:
            # 记录系统基本信息
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(output_dir)
            
            if memory.percent > 90:
                logger.warning(f"系统内存使用率较高 ({memory.percent}%)，可能影响处理性能")
                
            if disk.percent > 90:
                logger.warning(f"输出目录所在磁盘空间不足 ({disk.percent}% 已使用)，请确保有足够空间")
                
            if self.settings["hardware_accel"] != "none" and self.settings["hardware_accel"] != "auto":
                logger.info(f"使用硬件加速: {self.settings['hardware_accel']}")
        except Exception as e:
            logger.warning(f"检查系统状态时出错: {str(e)}")
        
        self.report_progress("正在扫描素材文件夹...", 0)
        
        # 扫描素材文件夹，获取视频和配音文件
        try:
            material_data = self._scan_material_folders(material_folders)
        except Exception as e:
            error_msg = f"扫描素材文件夹失败: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # 检查是否有可用素材
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
        
        for i in range(count):
            if self.stop_requested:
                logger.info("收到停止请求，中断视频合成")
                break
                
            try:
                # 生成单个视频
                output_path = os.path.join(output_dir, f"合成视频_{i+1}.mp4")
                self.report_progress(f"正在生成视频 {i+1}/{count}", 5 + progress_per_video * i)
                
                self._process_single_video(
                    material_data, 
                    output_path, 
                    bgm_path,
                    progress_start=5 + progress_per_video * i,
                    progress_end=5 + progress_per_video * (i + 1)
                )
                
                # 验证生成的视频文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    output_videos.append(output_path)
                    logger.info(f"成功生成视频: {output_path}")
                else:
                    logger.error(f"视频文件未正确生成或为空: {output_path}")
                
                self.report_progress(f"视频 {i+1}/{count} 生成完成", 5 + progress_per_video * (i + 1))
            except Exception as e:
                logger.error(f"生成视频 {i+1}/{count} 失败: {str(e)}")
                self.report_progress(f"视频 {i+1}/{count} 生成失败: {str(e)}", 5 + progress_per_video * i)
        
        # 如果一个视频都没有生成，抛出异常
        if not output_videos:
            error_msg = "没有成功生成任何视频，请检查日志获取详细错误信息"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.report_progress(f"批量视频处理完成，成功生成: {len(output_videos)}/{count}", 100)
        logger.info(f"批量视频处理完成，成功生成: {len(output_videos)}/{count}")
        
        return output_videos
    
    def stop_processing(self):
        """停止处理"""
        self.stop_requested = True
        logger.info("已请求停止视频处理")
    
    def _scan_material_folders(self, material_folders: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        扫描素材文件夹，获取视频和配音文件
        
        支持两种导入模式：
        1. 直接导入独立场景文件夹（原有模式）
        2. 导入父文件夹，从中提取按顺序排列的子文件夹作为场景（新模式）
        
        Args:
            material_folders: 素材文件夹信息列表
            
        Returns:
            Dict[str, Dict[str, Any]]: 素材数据，按子文件夹顺序排列
        """
        material_data = {}
        
        # 计算每个文件夹的扫描进度
        progress_per_folder = 4.0 / len(material_folders) if material_folders else 0
        
        for idx, folder_info in enumerate(material_folders):
            folder_path = folder_info["path"]
            folder_name = os.path.basename(folder_path)
            
            self.report_progress(f"正在扫描素材文件夹: {folder_name}", 1 + progress_per_folder * idx)
            
            # 检测是否为父文件夹导入模式（检查是否包含子文件夹）
            is_parent_folder = False
            sub_folders = []
            
            # 获取子文件夹列表
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path):
                    # 检查子文件夹是否包含标准结构（视频文件夹或配音文件夹）
                    video_dir = os.path.join(item_path, "视频")
                    audio_dir = os.path.join(item_path, "配音")
                    if os.path.isdir(video_dir) or os.path.isdir(audio_dir):
                        sub_folders.append(item_path)
            
            # 如果找到符合条件的子文件夹，认为是父文件夹导入模式
            if sub_folders:
                is_parent_folder = True
                logger.info(f"检测到父文件夹导入模式，找到 {len(sub_folders)} 个子文件夹")
                
                # 对子文件夹按名称排序，确保按正确顺序处理
                sub_folders.sort()
                
                # 逐个处理子文件夹
                for sub_idx, sub_path in enumerate(sub_folders):
                    sub_name = os.path.basename(sub_path)
                    self.report_progress(f"扫描段落 {sub_idx+1}/{len(sub_folders)}: {sub_name}", 
                                      1 + progress_per_folder * idx + (progress_per_folder * sub_idx / len(sub_folders)))
                    
                    # 使用顺序编号作为键，确保段落按顺序排列
                    segment_key = f"{sub_idx+1:02d}_{sub_name}"
                    
                    # 初始化段落数据
                    material_data[segment_key] = {
                        "videos": [],
                        "audios": [],
                        "path": sub_path,
                        "segment_index": sub_idx,  # 存储段落索引，用于排序
                        "parent_folder": folder_name  # 记录所属父文件夹
                    }
                    
                    # 扫描视频文件夹
                    self._scan_media_folder(sub_path, segment_key, material_data)
            else:
                # 原始模式：直接扫描所提供的文件夹
                # 初始化素材数据
                material_data[folder_name] = {
                    "videos": [],
                    "audios": [],
                    "path": folder_path
                }
                
                # 扫描视频文件夹
                self._scan_media_folder(folder_path, folder_name, material_data)
        
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
            material_data: 素材数据，包含各场景的视频和配音信息
            output_path: 输出视频路径
            bgm_path: 背景音乐路径
            progress_start: 进度条开始百分比
            progress_end: 进度条结束百分比
            
        Returns:
            str: 生成的视频文件路径
        """
        logger.info(f"开始处理视频，输出路径: {output_path}")
        
        if self.stop_requested:
            logger.info("收到停止请求，中断视频合成")
            raise InterruptedError("视频处理被用户中断")
        
        # 计算进度范围
        progress_range = progress_end - progress_start
        
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
                        clip_duration = max(audio_duration, min(video_duration, audio_duration + 1))
                        
                        # 如果视频比配音长，则从视频中间部分开始截取
                        if video_duration > clip_duration:
                            start_time = (video_duration - clip_duration) / 2
                            video_clip = video_clip.subclip(start_time, start_time + clip_duration)
                        
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
                    
                    logger.info(f"将使用FFmpeg直接编码，编码器: {codec}")
                    logger.info(f"硬件加速配置: {self.settings['hardware_accel']}")
                    logger.info(f"编码器设置: {self.settings['encoder']}")
                    
                    # 先导出为临时视频（无特殊编码）
                    progress_thread = threading.Thread(target=progress_monitor)
                    progress_thread.daemon = True
                    progress_thread.start()
                    
                    # 导出视频但使用快速编码，不使用特殊硬件加速
                    final_clip.write_videofile(
                        temp_raw_video, 
                        fps=30, 
                        codec="libx264",
                        audio_codec="aac",
                        remove_temp=True,
                        write_logfile=False,
                        preset="ultrafast", 
                        verbose=False,
                        threads=self.settings["threads"]
                    )
                    
                    # 再使用FFmpeg进行硬件加速编码
                    if os.path.exists(temp_raw_video):
                        success = self._encode_with_ffmpeg(temp_raw_video, output_path, codec)
                        
                        # 如果成功，删除临时文件并返回
                        if success:
                            try:
                                os.remove(temp_raw_video)
                            except Exception as e:
                                logger.warning(f"无法删除临时文件: {str(e)}")
                            
                            logger.info(f"使用FFmpeg硬件加速导出视频成功: {output_path}")
                            self.report_progress("视频导出完成", progress_end)
                            return output_path
                        else:
                            logger.warning("硬件加速失败，回退到标准编码")
                
                # 创建临时音频文件路径
                temp_audiofile = self._create_temp_file("temp_audio", ".m4a")
                
                # 进度更新线程
                export_start_time = time.time()
                def progress_monitor():
                    """监控视频导出进度的线程函数"""
                    last_progress = 0
                    while not self.stop_requested and os.path.exists(temp_audiofile):
                        try:
                            # 尝试预估进度
                            elapsed_time = time.time() - export_start_time
                            if final_clip.duration > 0:
                                # 以实际经过时间预估进度，假设导出处理速度为实时速度的2-5倍
                                # 这只是估计值，因为实际导出速度取决于硬件性能和视频复杂度
                                est_progress = min(0.95, elapsed_time / (final_clip.duration * 3))
                                if est_progress > last_progress:
                                    last_progress = est_progress
                                    percent = progress_start + progress_range * (0.8 + 0.15 * est_progress)
                                    self.report_progress(f"正在导出视频... {int(est_progress * 100)}%", percent)
                        except Exception as e:
                            logger.error(f"进度监控错误: {str(e)}")
                        
                        # 每秒更新一次进度
                        time.sleep(1)
                
                # 启动进度监控线程
                progress_thread = threading.Thread(target=progress_monitor)
                progress_thread.daemon = True
                progress_thread.start()
                
                # 导出视频
                final_clip.write_videofile(
                    output_path, 
                    fps=30, 
                    codec=codec,
                    audio_codec=audio_codec,
                    temp_audiofile=temp_audiofile,
                    remove_temp=True,
                    write_logfile=False,
                    preset="fast", 
                    verbose=False,
                    **export_params
                )
                
                # 检查视频是否成功导出
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    error_msg = f"导出视频失败: {output_path} 文件不存在或为空"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                    
                logger.info(f"视频导出成功: {output_path}")
                self.report_progress("视频导出完成", progress_end)
                
                return output_path
            except Exception as e:
                logger.error(f"导出视频失败: {str(e)}")
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        logger.info(f"已删除失败的输出文件: {output_path}")
                    except Exception as remove_error:
                        logger.warning(f"无法删除失败的输出文件: {str(remove_error)}")
                raise RuntimeError(f"导出视频失败: {str(e)}")
        finally:
            # 关闭所有资源，防止内存泄漏和文件句柄泄漏
            error_count = 0
            for resource in open_resources:
                try:
                    if hasattr(resource, 'close'):
                        resource.close()
                except Exception as e:
                    error_count += 1
                    logger.error(f"关闭资源时出错: {str(e)}")
            
            # 关闭选定片段中的所有剪辑资源
            for clip_info in selected_clips:
                try:
                    if 'clip' in clip_info and hasattr(clip_info['clip'], 'close'):
                        clip_info['clip'].close()
                except Exception as e:
                    error_count += 1
                    logger.error(f"关闭剪辑资源时出错: {str(e)}")
            
            if error_count > 0:
                logger.warning(f"关闭资源时发生 {error_count} 个错误，可能导致内存泄漏")
            else:
                logger.info("所有视频处理资源已正确释放")
    
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
        temp_dir = self.settings["temp_dir"]
        os.makedirs(temp_dir, exist_ok=True)
        
        timestamp = int(time.time() * 1000)
        random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=6))
        filename = f"{prefix}_{timestamp}_{random_str}{suffix}"
        
        return os.path.join(temp_dir, filename)
    
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
        判断是否应该使用直接FFmpeg命令进行硬件加速编码
        
        Args:
            codec: 编码器名称
            
        Returns:
            bool: 是否应该使用直接FFmpeg命令
        """
        # 对于NVENC编码器，始终使用直接FFmpeg命令以确保GPU加速
        if "nvenc" in codec:
            logger.info(f"检测到NVENC编码器 {codec}，将使用直接FFmpeg硬件加速")
            return True
        
        # 只对特定的硬件加速编码器使用直接FFmpeg命令
        return codec in ["h264_nvenc", "h264_qsv", "h264_amf", "hevc_nvenc"]
    
    def _encode_with_ffmpeg(self, input_path, output_path, codec):
        """
        使用FFmpeg直接进行视频编码，充分利用硬件加速
        
        Args:
            input_path: 输入视频文件路径
            output_path: 输出视频文件路径
            codec: 编码器名称
            
        Returns:
            bool: 是否成功
        """
        import subprocess
        
        # 构建FFmpeg命令
        ffmpeg_cmd = self._get_ffmpeg_cmd()
        
        # 修复强制使用NVENC编码
        if "h264" in codec and not "nvenc" in codec and "nvidia" in self.settings.get("encoder", "").lower():
            codec = "h264_nvenc"
            logger.info(f"检测到NVIDIA设置，强制使用h264_nvenc编码器")
        
        # 检查是否启用了兼容模式
        compatibility_mode = True  # 默认启用兼容模式
        gpu_config = None
        try:
            # 尝试从配置中读取兼容模式设置
            from src.hardware.gpu_config import GPUConfig
            gpu_config = GPUConfig()
            compatibility_mode = gpu_config.is_compatibility_mode_enabled()
            logger.info(f"GPU兼容模式设置: {'启用' if compatibility_mode else '禁用'}")
        except Exception as e:
            logger.warning(f"读取GPU兼容模式设置时出错: {str(e)}，将使用默认兼容模式")
        
        logger.info(f"将使用编码器: {codec}")
        
        # GPU加速相关参数
        gpu_params = []
        # NVENC特殊参数
        if "nvenc" in codec:
            # 始终使用兼容模式参数
            logger.info("使用NVENC编码 - 兼容模式参数")
            gpu_params = [
                "-c:v", codec,
                "-preset", "p4",  # 兼容性好的预设
                "-b:v", f"{self.settings['bitrate']}k",
                "-spatial-aq", "1",  # 保留基础的自适应量化
                "-temporal-aq", "1",  # 保留基础的时间自适应量化
                "-gpu", "0"          # 显式指定使用第一个GPU
            ]
        # QSV特殊参数
        elif codec == "h264_qsv":
            gpu_params = [
                "-c:v", codec,
                "-preset", "medium",
                "-global_quality", "23",
                "-b:v", f"{self.settings['bitrate']}k"
            ]
        # AMF特殊参数
        elif codec == "h264_amf":
            gpu_params = [
                "-c:v", codec,
                "-quality", "quality",
                "-usage", "transcoding",
                "-b:v", f"{self.settings['bitrate']}k"
            ]
        else:
            # 其他编码器使用基本参数
            gpu_params = [
                "-c:v", codec,
                "-b:v", f"{self.settings['bitrate']}k"
            ]
        
        # 通用参数
        common_params = [
            "-i", input_path,
            "-c:a", "aac",  # 音频编码器
            "-b:a", "192k", # 音频比特率
            "-y"            # 覆盖输出文件
        ]
        
        # 如果指定了线程数
        thread_params = []
        if self.settings["threads"] > 0:
            thread_params = ["-threads", str(self.settings["threads"])]
        
        # 组合完整命令
        cmd = [ffmpeg_cmd] + common_params + gpu_params + thread_params + [output_path]
        
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
            
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1,
                    text=True
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
                            info_cmd = [ffmpeg_cmd, "-i", output_path]
                            info_proc = subprocess.Popen(
                                info_cmd, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                universal_newlines=True
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
                        with open(log_file, 'r') as f:
                            last_lines = "".join(f.readlines()[-20:])  # 读取最后20行
                            logger.error(f"FFmpeg错误输出: {last_lines}")
                    except Exception:
                        pass
                        
                    return False
        except Exception as e:
            logger.error(f"执行FFmpeg命令时出错: {str(e)}")
            return False
    
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
                with open(ffmpeg_path_file, 'r') as f:
                    custom_path = f.read().strip()
                    if custom_path and os.path.exists(custom_path):
                        logger.info(f"使用自定义FFmpeg路径: {custom_path}")
                        return custom_path
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