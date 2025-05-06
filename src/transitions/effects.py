#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
转场效果实现模块
包含各种视频转场效果，用于防重复检测的视频混剪
"""

import random
import numpy as np
from typing import Callable, Dict, List, Tuple, Union

try:
    import cv2
    from moviepy.editor import VideoClip, VideoFileClip, CompositeVideoClip
    from moviepy.video.fx import fadein, fadeout
except ImportError as e:
    raise ImportError(f"请安装必要的依赖: {e}")

from utils.logger import get_logger

logger = get_logger()

class TransitionEffect:
    """转场效果基类"""
    
    def __init__(self, duration: float = 1.0):
        """
        初始化转场效果
        
        Args:
            duration: 转场时长(秒)
        """
        self.duration = duration
        self.name = "基础转场"
        self.description = "基础转场效果"
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """
        应用转场效果
        
        Args:
            clip1: 第一个视频片段
            clip2: 第二个视频片段
            
        Returns:
            VideoClip: 应用转场效果后的视频片段
        """
        # 基类不实现具体效果，只是淡入淡出
        clip1 = clip1.fx(fadeout, self.duration)
        clip2 = clip2.fx(fadein, self.duration)
        
        # 计算转场起始时间
        transition_start = max(0, clip1.duration - self.duration)
        
        # 创建合成视频
        result = CompositeVideoClip([
            clip1,
            clip2.set_start(transition_start)
        ])
        
        return result

class FadeTransition(TransitionEffect):
    """淡入淡出转场效果"""
    
    def __init__(self, duration: float = 1.0):
        super().__init__(duration)
        self.name = "淡入淡出"
        self.description = "经典的淡入淡出转场效果"
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用淡入淡出效果"""
        # 直接调用基类的实现
        return super().apply(clip1, clip2)

class MirrorFlipTransition(TransitionEffect):
    """镜像翻转转场效果"""
    
    def __init__(self, duration: float = 1.0, direction: str = "horizontal"):
        """
        初始化镜像翻转转场
        
        Args:
            duration: 转场时长(秒)
            direction: 翻转方向，"horizontal"或"vertical"
        """
        super().__init__(duration)
        self.name = "镜像翻转"
        self.description = "视频画面翻转过渡，可以是水平或垂直翻转"
        self.direction = direction
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用镜像翻转效果"""
        # 定义翻转效果函数
        def flip_effect(get_frame, t):
            """翻转效果"""
            progress = min(1, max(0, (t - (clip1.duration - self.duration)) / self.duration))
            
            if t < clip1.duration:
                frame = get_frame(t)
                
                if progress > 0:
                    # 应用翻转效果
                    if self.direction == "horizontal":
                        # 水平翻转
                        flip_width = int(frame.shape[1] * progress)
                        if flip_width > 0:
                            frame[:, :flip_width] = cv2.flip(frame[:, :flip_width], 1)
                    else:
                        # 垂直翻转
                        flip_height = int(frame.shape[0] * progress)
                        if flip_height > 0:
                            frame[:flip_height, :] = cv2.flip(frame[:flip_height, :], 0)
                
                return frame
            else:
                # 第二个视频的帧
                t2 = t - clip1.duration + self.duration
                frame = clip2.get_frame(t2)
                
                if progress < 1:
                    # 继续应用翻转效果到第二个视频
                    if self.direction == "horizontal":
                        # 水平翻转
                        flip_width = int(frame.shape[1] * (1 - progress))
                        if flip_width > 0:
                            frame[:, -flip_width:] = cv2.flip(frame[:, -flip_width:], 1)
                    else:
                        # 垂直翻转
                        flip_height = int(frame.shape[0] * (1 - progress))
                        if flip_height > 0:
                            frame[-flip_height:, :] = cv2.flip(frame[-flip_height:, :], 0)
                
                return frame
        
        # 创建新的视频片段
        new_duration = clip1.duration + clip2.duration - self.duration
        new_clip = VideoClip(flip_effect, duration=new_duration)
        
        # 合并音频
        if clip1.audio and clip2.audio:
            new_clip = new_clip.set_audio(clip1.audio)
        
        return new_clip

class HueShiftTransition(TransitionEffect):
    """色相偏移转场效果"""
    
    def __init__(self, duration: float = 1.0, shift_amount: float = 180.0):
        """
        初始化色相偏移转场
        
        Args:
            duration: 转场时长(秒)
            shift_amount: 色相偏移量(0-360度)
        """
        super().__init__(duration)
        self.name = "色相偏移"
        self.description = "通过改变色相实现画面渐变过渡"
        self.shift_amount = shift_amount
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用色相偏移效果"""
        # 定义色相偏移效果函数
        def hue_shift_effect(get_frame, t):
            """色相偏移效果"""
            progress = min(1, max(0, (t - (clip1.duration - self.duration)) / self.duration))
            
            if t < clip1.duration:
                frame = get_frame(t)
                
                if progress > 0:
                    # 转换到HSV色彩空间
                    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
                    
                    # 应用色相偏移
                    hsv[:, :, 0] += self.shift_amount * progress
                    hsv[:, :, 0] %= 180  # OpenCV中H的范围是0-180
                    
                    # 转换回RGB
                    frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
                
                return frame
            else:
                # 第二个视频的帧
                t2 = t - clip1.duration + self.duration
                frame = clip2.get_frame(t2)
                
                if progress < 1:
                    # 转换到HSV色彩空间
                    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
                    
                    # 应用色相偏移
                    hsv[:, :, 0] += self.shift_amount * (1 - progress)
                    hsv[:, :, 0] %= 180  # OpenCV中H的范围是0-180
                    
                    # 转换回RGB
                    frame = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
                
                return frame
        
        # 创建新的视频片段
        new_duration = clip1.duration + clip2.duration - self.duration
        new_clip = VideoClip(hue_shift_effect, duration=new_duration)
        
        # 合并音频
        if clip1.audio and clip2.audio:
            new_clip = new_clip.set_audio(clip1.audio)
        
        return new_clip

class PixelateTransition(TransitionEffect):
    """像素化转场效果"""
    
    def __init__(self, duration: float = 1.0, min_pixel_size: int = 1, max_pixel_size: int = 20):
        """
        初始化像素化转场
        
        Args:
            duration: 转场时长(秒)
            min_pixel_size: 最小像素块大小
            max_pixel_size: 最大像素块大小
        """
        super().__init__(duration)
        self.name = "像素化过渡"
        self.description = "画面逐渐像素化然后还原的过渡效果"
        self.min_pixel_size = min_pixel_size
        self.max_pixel_size = max_pixel_size
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用像素化效果"""
        # 定义像素化效果函数
        def pixelate_effect(get_frame, t):
            """像素化效果"""
            progress = min(1, max(0, (t - (clip1.duration - self.duration)) / self.duration))
            
            # 像素大小随进度变化，先增加后减小
            if progress < 0.5:
                pixel_size = int(self.min_pixel_size + (self.max_pixel_size - self.min_pixel_size) * (progress * 2))
            else:
                pixel_size = int(self.min_pixel_size + (self.max_pixel_size - self.min_pixel_size) * ((1 - progress) * 2))
            
            if t < clip1.duration:
                frame = get_frame(t)
                
                if progress > 0:
                    # 应用像素化效果
                    if pixel_size > 1:
                        h, w = frame.shape[:2]
                        temp = cv2.resize(frame, (w // pixel_size, h // pixel_size), interpolation=cv2.INTER_LINEAR)
                        frame = cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)
                
                return frame
            else:
                # 第二个视频的帧
                t2 = t - clip1.duration + self.duration
                frame = clip2.get_frame(t2)
                
                if progress < 1:
                    # 应用像素化效果
                    if pixel_size > 1:
                        h, w = frame.shape[:2]
                        temp = cv2.resize(frame, (w // pixel_size, h // pixel_size), interpolation=cv2.INTER_LINEAR)
                        frame = cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)
                
                return frame
        
        # 创建新的视频片段
        new_duration = clip1.duration + clip2.duration - self.duration
        new_clip = VideoClip(pixelate_effect, duration=new_duration)
        
        # 合并音频
        if clip1.audio and clip2.audio:
            new_clip = new_clip.set_audio(clip1.audio)
        
        return new_clip

class SpinZoomTransition(TransitionEffect):
    """旋转缩放转场效果"""
    
    def __init__(self, duration: float = 1.0, max_angle: float = 10.0, max_zoom: float = 1.2):
        """
        初始化旋转缩放转场
        
        Args:
            duration: 转场时长(秒)
            max_angle: 最大旋转角度
            max_zoom: 最大缩放比例
        """
        super().__init__(duration)
        self.name = "轻微旋转缩放"
        self.description = "画面轻微旋转和缩放的过渡效果"
        self.max_angle = max_angle
        self.max_zoom = max_zoom
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用旋转缩放效果"""
        # 定义旋转缩放效果函数
        def spin_zoom_effect(get_frame, t):
            """旋转缩放效果"""
            progress = min(1, max(0, (t - (clip1.duration - self.duration)) / self.duration))
            
            if t < clip1.duration:
                frame = get_frame(t)
                
                if progress > 0:
                    # 计算旋转角度和缩放比例
                    angle = self.max_angle * progress
                    zoom = 1 + (self.max_zoom - 1) * progress
                    
                    # 应用旋转和缩放
                    h, w = frame.shape[:2]
                    center = (w / 2, h / 2)
                    rotation_matrix = cv2.getRotationMatrix2D(center, angle, zoom)
                    frame = cv2.warpAffine(frame, rotation_matrix, (w, h))
                
                return frame
            else:
                # 第二个视频的帧
                t2 = t - clip1.duration + self.duration
                frame = clip2.get_frame(t2)
                
                if progress < 1:
                    # 计算旋转角度和缩放比例
                    angle = self.max_angle * (1 - progress)
                    zoom = 1 + (self.max_zoom - 1) * (1 - progress)
                    
                    # 应用旋转和缩放
                    h, w = frame.shape[:2]
                    center = (w / 2, h / 2)
                    rotation_matrix = cv2.getRotationMatrix2D(center, -angle, zoom)  # 反向旋转
                    frame = cv2.warpAffine(frame, rotation_matrix, (w, h))
                
                return frame
        
        # 创建新的视频片段
        new_duration = clip1.duration + clip2.duration - self.duration
        new_clip = VideoClip(spin_zoom_effect, duration=new_duration)
        
        # 合并音频
        if clip1.audio and clip2.audio:
            new_clip = new_clip.set_audio(clip1.audio)
        
        return new_clip

class ReverseFlashbackTransition(TransitionEffect):
    """倒放闪回转场效果"""
    
    def __init__(self, duration: float = 1.0, flash_count: int = 3):
        """
        初始化倒放闪回转场
        
        Args:
            duration: 转场时长(秒)
            flash_count: 闪烁次数
        """
        super().__init__(duration)
        self.name = "倒放闪回"
        self.description = "视频短暂倒放并闪烁的过渡效果"
        self.flash_count = flash_count
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用倒放闪回效果"""
        # 定义倒放闪回效果函数
        def reverse_flashback_effect(get_frame, t):
            """倒放闪回效果"""
            progress = min(1, max(0, (t - (clip1.duration - self.duration)) / self.duration))
            
            # 闪烁效果
            flash_phase = progress * self.flash_count
            flash_intensity = abs(flash_phase - int(flash_phase) - 0.5) * 2  # 生成0-1-0的波形
            
            if t < clip1.duration:
                # 在第一个视频结束前，可能需要获取倒放的帧
                if progress > 0.5:
                    # 用第二个视频的开始部分
                    second_progress = (progress - 0.5) * 2  # 0到1
                    rev_time = second_progress * self.duration * 0.5
                    frame = clip2.get_frame(rev_time)
                else:
                    # 用第一个视频的末尾部分，可能需要倒放
                    first_progress = progress * 2  # 0到1
                    time_from_end = first_progress * self.duration * 0.5
                    frame = get_frame(clip1.duration - time_from_end)
                
                # 应用闪烁效果
                if flash_intensity > 0:
                    brightness = 1.0 + flash_intensity * 0.5  # 增加亮度
                    frame = np.clip(frame * brightness, 0, 255).astype(np.uint8)
                
                return frame
            else:
                # 第二个视频的帧
                t2 = t - clip1.duration + self.duration
                frame = clip2.get_frame(t2)
                
                # 过渡结束后，可能仍需应用闪烁效果
                if progress < 1 and flash_intensity > 0:
                    brightness = 1.0 + flash_intensity * 0.5
                    frame = np.clip(frame * brightness, 0, 255).astype(np.uint8)
                
                return frame
        
        # 创建新的视频片段
        new_duration = clip1.duration + clip2.duration - self.duration
        new_clip = VideoClip(reverse_flashback_effect, duration=new_duration)
        
        # 合并音频
        if clip1.audio and clip2.audio:
            new_clip = new_clip.set_audio(clip1.audio)
        
        return new_clip

class SpeedRampTransition(TransitionEffect):
    """速度波动转场效果"""
    
    def __init__(self, duration: float = 1.0, max_speedup: float = 2.0):
        """
        初始化速度波动转场
        
        Args:
            duration: 转场时长(秒)
            max_speedup: 最大加速倍率
        """
        super().__init__(duration)
        self.name = "速度波动过渡"
        self.description = "视频速度先加快后减慢的过渡效果"
        self.max_speedup = max_speedup
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用速度波动效果"""
        # 这个效果会改变视频播放速度，需要预先处理
        # 注意：由于是变速效果，无法简单地通过逐帧处理实现
        # 实际应用中应该使用moviepy的专门的速度变化功能
        
        # 第一个片段增加速度
        end_time = clip1.duration - self.duration / 2
        speedup_duration = min(self.duration / 2, end_time)
        
        if speedup_duration > 0:
            # 创建前半部分
            front_part = clip1.subclip(0, end_time - speedup_duration)
            
            # 创建变速部分
            def speedup_time_warp(t):
                return end_time - speedup_duration + t * (speedup_duration / (self.max_speedup * speedup_duration))
            
            speed_part = clip1.subclip(end_time - speedup_duration, end_time).fl_time(speedup_time_warp, 
                                                                                      keep_duration=False)
            
            # 合并前半部分和变速部分
            first_clip = concatenate_clips([front_part, speed_part]) if front_part.duration > 0 else speed_part
        else:
            first_clip = clip1
        
        # 第二个片段减缓速度
        slowdown_duration = min(self.duration / 2, clip2.duration)
        
        if slowdown_duration > 0:
            # 创建变速部分
            def slowdown_time_warp(t):
                return t * self.max_speedup
            
            speed_part = clip2.subclip(0, slowdown_duration / self.max_speedup).fl_time(slowdown_time_warp, 
                                                                                       keep_duration=True)
            
            # 创建后半部分
            back_part = clip2.subclip(slowdown_duration, clip2.duration)
            
            # 合并变速部分和后半部分
            second_clip = concatenate_clips([speed_part, back_part]) if back_part.duration > 0 else speed_part
        else:
            second_clip = clip2
        
        # 淡入淡出过渡
        first_clip = first_clip.fx(fadeout, min(0.5, first_clip.duration / 2))
        second_clip = second_clip.fx(fadein, min(0.5, second_clip.duration / 2))
        
        # 合并两个片段
        transition_start = max(0, first_clip.duration - min(0.5, first_clip.duration / 2))
        result = CompositeVideoClip([
            first_clip,
            second_clip.set_start(transition_start)
        ])
        
        return result

class SplitScreenTransition(TransitionEffect):
    """分屏滑动转场效果"""
    
    def __init__(self, duration: float = 1.0, direction: str = "horizontal"):
        """
        初始化分屏滑动转场
        
        Args:
            duration: 转场时长(秒)
            direction: 滑动方向，"horizontal"或"vertical"
        """
        super().__init__(duration)
        self.name = "分屏滑动"
        self.description = "画面分割并滑动过渡的效果"
        self.direction = direction
    
    def apply(self, clip1: VideoClip, clip2: VideoClip) -> VideoClip:
        """应用分屏滑动效果"""
        # 定义分屏滑动效果函数
        def split_screen_effect(get_frame, t):
            """分屏滑动效果"""
            progress = min(1, max(0, (t - (clip1.duration - self.duration)) / self.duration))
            
            if t < clip1.duration:
                frame1 = get_frame(t)
                h, w = frame1.shape[:2]
                
                if progress > 0:
                    # 获取第二个视频的帧
                    t2 = progress * self.duration
                    if t2 < clip2.duration:
                        frame2 = clip2.get_frame(t2)
                        
                        # 调整第二个帧的大小以匹配第一个
                        if frame2.shape[:2] != (h, w):
                            frame2 = cv2.resize(frame2, (w, h))
                        
                        # 应用分屏滑动效果
                        if self.direction == "horizontal":
                            # 水平滑动
                            split_pos = int(w * progress)
                            frame1[:, split_pos:] = frame2[:, split_pos:]
                        else:
                            # 垂直滑动
                            split_pos = int(h * progress)
                            frame1[split_pos:, :] = frame2[split_pos:, :]
                
                return frame1
            else:
                # 第二个视频的帧
                t2 = t - clip1.duration + self.duration
                frame2 = clip2.get_frame(t2)
                
                if progress < 1:
                    # 获取第一个视频的最后一帧
                    frame1 = clip1.get_frame(clip1.duration - 0.001)
                    h, w = frame1.shape[:2]
                    
                    # 调整第一个帧的大小以匹配第二个
                    if frame1.shape[:2] != frame2.shape[:2]:
                        h, w = frame2.shape[:2]
                        frame1 = cv2.resize(frame1, (w, h))
                    
                    # 应用分屏滑动效果
                    if self.direction == "horizontal":
                        # 水平滑动
                        split_pos = int(w * progress)
                        frame2[:, :split_pos] = frame1[:, :split_pos]
                    else:
                        # 垂直滑动
                        split_pos = int(h * progress)
                        frame2[:split_pos, :] = frame1[:split_pos, :]
                
                return frame2
        
        # 创建新的视频片段
        new_duration = clip1.duration + clip2.duration - self.duration
        new_clip = VideoClip(split_screen_effect, duration=new_duration)
        
        # 合并音频
        if clip1.audio and clip2.audio:
            new_clip = new_clip.set_audio(clip1.audio)
        
        return new_clip

def get_transition_effect(name: str, duration: float = 1.0) -> TransitionEffect:
    """
    获取指定名称的转场效果
    
    Args:
        name: 转场效果名称
        duration: 转场时长(秒)
        
    Returns:
        TransitionEffect: 转场效果对象
    """
    transitions = {
        "fade": FadeTransition(duration),
        "mirror_flip": MirrorFlipTransition(duration),
        "hue_shift": HueShiftTransition(duration),
        "pixelate": PixelateTransition(duration),
        "spin_zoom": SpinZoomTransition(duration),
        "reverse_flashback": ReverseFlashbackTransition(duration),
        "speed_ramp": SpeedRampTransition(duration),
        "split_screen": SplitScreenTransition(duration)
    }
    
    # 如果是随机选择，则从所有效果中随机一个
    if name == "random":
        return random.choice(list(transitions.values()))
    
    # 返回指定效果，如果不存在则返回默认的淡入淡出
    return transitions.get(name, FadeTransition(duration))

def get_all_transition_effects(duration: float = 1.0) -> Dict[str, TransitionEffect]:
    """
    获取所有可用的转场效果
    
    Args:
        duration: 转场时长(秒)
        
    Returns:
        Dict[str, TransitionEffect]: 转场效果字典
    """
    return {
        "fade": FadeTransition(duration),
        "mirror_flip": MirrorFlipTransition(duration),
        "hue_shift": HueShiftTransition(duration),
        "pixelate": PixelateTransition(duration),
        "spin_zoom": SpinZoomTransition(duration),
        "reverse_flashback": ReverseFlashbackTransition(duration),
        "speed_ramp": SpeedRampTransition(duration),
        "split_screen": SplitScreenTransition(duration)
    } 