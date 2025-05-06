#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
音频处理模块
用于处理视频混剪中的音频相关操作
"""

import os
import random
import tempfile
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union

try:
    import librosa
    import soundfile as sf
    from pydub import AudioSegment
    from moviepy.editor import AudioFileClip, CompositeAudioClip
except ImportError as e:
    raise ImportError(f"请安装必要的依赖: {e}")

from utils.logger import get_logger
from utils.cache_config import CacheConfig

logger = get_logger()

class AudioProcessor:
    """音频处理类，处理混剪过程中的音频操作"""
    
    def __init__(self, settings: Dict = None):
        """
        初始化音频处理器
        
        Args:
            settings: 音频处理设置
        """
        # 获取缓存配置
        cache_config = CacheConfig()
        cache_dir = cache_config.get_cache_dir()
        
        # 默认设置
        self.default_settings = {
            "sample_rate": 44100,        # 采样率
            "channels": 2,               # 声道数
            "format": "wav",             # 临时音频格式
            "voice_volume": 1.0,         # 配音音量
            "bgm_volume": 0.5,           # 背景音乐音量
            "fade_in": 0.5,              # 淡入时长(秒)
            "fade_out": 1.0,             # 淡出时长(秒)
            "temp_dir": cache_dir       # 使用配置的缓存目录
        }
        
        # 更新设置
        self.settings = self.default_settings.copy()
        if settings:
            self.settings.update(settings)
        
        # 确保临时目录存在
        os.makedirs(self.settings["temp_dir"], exist_ok=True)
    
    def extract_audio_from_video(self, video_path: str, output_path: str = None) -> str:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 提取的音频文件路径
        """
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("extracted_audio", f".{self.settings['format']}")
        
        try:
            logger.info(f"从视频提取音频: {video_path}")
            
            # 使用MoviePy提取音频
            audio_clip = AudioFileClip(video_path)
            audio_clip.write_audiofile(output_path, 
                                      fps=self.settings["sample_rate"], 
                                      nbytes=2,  # 16-bit
                                      codec='pcm_s16le' if self.settings["format"] == "wav" else None)
            audio_clip.close()
            
            logger.info(f"音频提取完成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"从视频提取音频失败: {str(e)}")
            raise
    
    def adjust_volume(self, audio_path: str, volume: float, output_path: str = None) -> str:
        """
        调整音频音量
        
        Args:
            audio_path: 音频文件路径
            volume: 音量倍数
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 处理后的音频文件路径
        """
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("volume_adjusted", f".{self.settings['format']}")
        
        try:
            logger.info(f"调整音频音量: {audio_path}, 音量倍数: {volume}")
            
            # 使用pydub调整音量
            audio = AudioSegment.from_file(audio_path)
            
            # 将音量调整为原来的volume倍
            # pydub中音量调整是通过dB值完成的，将线性倍数转换为dB值
            if volume > 0:
                db_change = 20 * np.log10(volume)
                adjusted_audio = audio.apply_gain(db_change)
                
                # 保存调整后的音频
                adjusted_audio.export(output_path, format=self.settings["format"])
                
                logger.info(f"音量调整完成: {output_path}")
                return output_path
            else:
                logger.warning(f"音量倍数为0或负值: {volume}，返回静音音频")
                # 生成相同长度的静音音频
                silent_audio = AudioSegment.silent(duration=len(audio))
                silent_audio.export(output_path, format=self.settings["format"])
                return output_path
        except Exception as e:
            logger.error(f"调整音频音量失败: {str(e)}")
            raise
    
    def mix_audio(self, audio_paths: List[str], volumes: List[float] = None, output_path: str = None) -> str:
        """
        混合多个音频文件
        
        Args:
            audio_paths: 音频文件路径列表
            volumes: 各音频的音量倍数列表，长度应与audio_paths相同
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 混合后的音频文件路径
        """
        if not audio_paths:
            raise ValueError("音频文件列表为空")
        
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("mixed_audio", f".{self.settings['format']}")
        
        # 如果没有提供音量列表，则使用默认值1.0
        if volumes is None:
            volumes = [1.0] * len(audio_paths)
        elif len(volumes) != len(audio_paths):
            raise ValueError("音量列表长度与音频文件列表长度不一致")
        
        try:
            logger.info(f"混合音频文件: {audio_paths}")
            
            # 加载第一个音频作为基础
            mixed_audio = AudioSegment.from_file(audio_paths[0])
            
            # 应用第一个音频的音量
            if volumes[0] != 1.0:
                db_change = 20 * np.log10(volumes[0])
                mixed_audio = mixed_audio.apply_gain(db_change)
            
            # 混合其余音频
            for i in range(1, len(audio_paths)):
                audio = AudioSegment.from_file(audio_paths[i])
                
                # 应用音量
                if volumes[i] != 1.0:
                    db_change = 20 * np.log10(volumes[i])
                    audio = audio.apply_gain(db_change)
                
                # 如果音频长度不同，以较长的为准
                if len(audio) > len(mixed_audio):
                    # 将基础音频延长到与当前音频相同长度
                    silence = AudioSegment.silent(duration=len(audio) - len(mixed_audio))
                    mixed_audio = mixed_audio + silence
                
                # 叠加音频（音频混合）
                mixed_audio = mixed_audio.overlay(audio, position=0)
            
            # 保存混合后的音频
            mixed_audio.export(output_path, format=self.settings["format"])
            
            logger.info(f"音频混合完成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"混合音频失败: {str(e)}")
            raise
    
    def add_bgm(self, audio_path: str, bgm_path: str, voice_volume: float = None, bgm_volume: float = None,
                output_path: str = None) -> str:
        """
        为配音添加背景音乐
        
        Args:
            audio_path: 配音文件路径
            bgm_path: 背景音乐文件路径
            voice_volume: 配音音量，如果为None则使用默认设置
            bgm_volume: 背景音乐音量，如果为None则使用默认设置
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 添加背景音乐后的音频文件路径
        """
        if voice_volume is None:
            voice_volume = self.settings["voice_volume"]
        
        if bgm_volume is None:
            bgm_volume = self.settings["bgm_volume"]
        
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("audio_with_bgm", f".{self.settings['format']}")
        
        try:
            logger.info(f"为配音添加背景音乐: {audio_path}, BGM: {bgm_path}")
            
            # 加载配音和背景音乐
            voice = AudioSegment.from_file(audio_path)
            bgm = AudioSegment.from_file(bgm_path)
            
            # 应用淡入淡出效果到背景音乐
            fade_in_ms = int(self.settings["fade_in"] * 1000)
            fade_out_ms = int(self.settings["fade_out"] * 1000)
            
            if len(bgm) > fade_in_ms:
                bgm = bgm.fade_in(fade_in_ms)
            
            if len(bgm) > fade_out_ms:
                bgm = bgm.fade_out(fade_out_ms)
            
            # 循环背景音乐以匹配配音长度
            while len(bgm) < len(voice):
                bgm = bgm + bgm
            
            # 裁剪背景音乐以匹配配音长度
            bgm = bgm[:len(voice)]
            
            # 调整音量
            voice_db_change = 20 * np.log10(voice_volume)
            bgm_db_change = 20 * np.log10(bgm_volume)
            
            voice = voice.apply_gain(voice_db_change)
            bgm = bgm.apply_gain(bgm_db_change)
            
            # 混合配音和背景音乐
            mixed_audio = voice.overlay(bgm)
            
            # 保存混合后的音频
            mixed_audio.export(output_path, format=self.settings["format"])
            
            logger.info(f"添加背景音乐完成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"添加背景音乐失败: {str(e)}")
            raise
    
    def detect_silence(self, audio_path: str, min_silence_len: int = 500, silence_thresh: float = -40) -> List[Tuple[float, float]]:
        """
        检测音频中的静音部分
        
        Args:
            audio_path: 音频文件路径
            min_silence_len: 最小静音长度(毫秒)
            silence_thresh: 静音阈值(dB)
            
        Returns:
            List[Tuple[float, float]]: 静音片段列表，每个元素为(开始时间, 结束时间)，单位为秒
        """
        try:
            logger.info(f"检测音频静音部分: {audio_path}")
            
            # 加载音频
            audio = AudioSegment.from_file(audio_path)
            
            # 使用pydub检测静音
            from pydub.silence import detect_silence
            silence_millis = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
            
            # 将毫秒转换为秒
            silence_secs = [(start / 1000.0, end / 1000.0) for start, end in silence_millis]
            
            logger.info(f"检测到 {len(silence_secs)} 个静音片段")
            return silence_secs
        except Exception as e:
            logger.error(f"检测音频静音部分失败: {str(e)}")
            raise
    
    def auto_split_audio(self, audio_path: str, output_dir: str, min_silence_len: int = 700, 
                         silence_thresh: float = -40, min_segment_len: float = 1.0) -> List[str]:
        """
        根据静音自动切分音频
        
        Args:
            audio_path: 音频文件路径
            output_dir: 输出目录
            min_silence_len: 最小静音长度(毫秒)
            silence_thresh: 静音阈值(dB)
            min_segment_len: 最小片段长度(秒)
            
        Returns:
            List[str]: 切分后的音频文件路径列表
        """
        try:
            logger.info(f"自动切分音频: {audio_path}")
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 加载音频
            audio = AudioSegment.from_file(audio_path)
            
            # 检测静音片段
            silence_ranges = self.detect_silence(audio_path, min_silence_len, silence_thresh)
            
            if not silence_ranges:
                logger.warning(f"未检测到静音片段，无法切分音频")
                return [audio_path]
            
            # 根据静音片段切分音频
            audio_segments = []
            current_position = 0
            
            for i, (silence_start, silence_end) in enumerate(silence_ranges):
                # 将时间从秒转换为毫秒
                silence_start_ms = int(silence_start * 1000)
                silence_end_ms = int(silence_end * 1000)
                
                # 提取静音前的片段
                if silence_start_ms > current_position:
                    segment = audio[current_position:silence_start_ms]
                    
                    # 只保留长度超过最小片段长度的部分
                    if len(segment) / 1000 >= min_segment_len:
                        segment_path = os.path.join(output_dir, f"segment_{len(audio_segments)+1}.{self.settings['format']}")
                        segment.export(segment_path, format=self.settings["format"])
                        audio_segments.append(segment_path)
                
                # 更新当前位置
                current_position = silence_end_ms
            
            # 处理最后一个静音后的部分
            if current_position < len(audio):
                segment = audio[current_position:]
                
                if len(segment) / 1000 >= min_segment_len:
                    segment_path = os.path.join(output_dir, f"segment_{len(audio_segments)+1}.{self.settings['format']}")
                    segment.export(segment_path, format=self.settings["format"])
                    audio_segments.append(segment_path)
            
            logger.info(f"音频切分完成，共 {len(audio_segments)} 个片段")
            return audio_segments
        except Exception as e:
            logger.error(f"自动切分音频失败: {str(e)}")
            raise
    
    def change_pitch(self, audio_path: str, semitones: float, output_path: str = None) -> str:
        """
        改变音频音调
        
        Args:
            audio_path: 音频文件路径
            semitones: 音调变化半音数（正数升调，负数降调）
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 处理后的音频文件路径
        """
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("pitch_changed", f".{self.settings['format']}")
        
        try:
            logger.info(f"改变音频音调: {audio_path}, 半音数: {semitones}")
            
            # 使用librosa进行音调变化
            y, sr = librosa.load(audio_path, sr=None)
            
            # 改变音调
            y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones)
            
            # 保存音频
            sf.write(output_path, y_shifted, sr)
            
            logger.info(f"音调变化完成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"改变音频音调失败: {str(e)}")
            raise
    
    def change_tempo(self, audio_path: str, tempo_factor: float, output_path: str = None) -> str:
        """
        改变音频速度（不改变音调）
        
        Args:
            audio_path: 音频文件路径
            tempo_factor: 速度因子（大于1加速，小于1减速）
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 处理后的音频文件路径
        """
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("tempo_changed", f".{self.settings['format']}")
        
        try:
            logger.info(f"改变音频速度: {audio_path}, 速度因子: {tempo_factor}")
            
            # 使用librosa进行速度变化
            y, sr = librosa.load(audio_path, sr=None)
            
            # 改变速度但保持音调
            y_stretched = librosa.effects.time_stretch(y, rate=tempo_factor)
            
            # 保存音频
            sf.write(output_path, y_stretched, sr)
            
            logger.info(f"速度变化完成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"改变音频速度失败: {str(e)}")
            raise
    
    def normalize_audio(self, audio_path: str, target_db: float = -6.0, output_path: str = None) -> str:
        """
        规范化音频音量
        
        Args:
            audio_path: 音频文件路径
            target_db: 目标分贝值
            output_path: 输出音频路径，如果为None则生成临时文件
            
        Returns:
            str: 处理后的音频文件路径
        """
        if output_path is None:
            # 创建临时音频文件
            output_path = self._create_temp_file("normalized", f".{self.settings['format']}")
        
        try:
            logger.info(f"规范化音频音量: {audio_path}, 目标分贝值: {target_db}")
            
            # 加载音频
            audio = AudioSegment.from_file(audio_path)
            
            # 获取当前音量
            current_db = audio.dBFS
            
            # 计算需要调整的分贝差值
            db_change = target_db - current_db
            
            # 应用音量变化
            normalized_audio = audio.apply_gain(db_change)
            
            # 保存规范化后的音频
            normalized_audio.export(output_path, format=self.settings["format"])
            
            logger.info(f"音频规范化完成: {output_path}, 调整了 {db_change:.2f} dB")
            return output_path
        except Exception as e:
            logger.error(f"规范化音频音量失败: {str(e)}")
            raise
    
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
        
        # 创建唯一的临时文件名
        temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=f"{prefix}_", suffix=suffix, dir=temp_dir)
        temp_file.close()
        
        return temp_file.name
    
    def clean_temp_files(self):
        """清理临时文件"""
        temp_dir = self.settings["temp_dir"]
        
        if os.path.exists(temp_dir):
            try:
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                
                logger.info("音频临时文件清理完成")
            except Exception as e:
                logger.error(f"清理音频临时文件失败: {str(e)}") 