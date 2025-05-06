#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频合成失败修复工具

用于修复视频混剪工具中合成过程只有1秒钟的问题
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

# 获取用户主目录
USER_HOME = os.path.expanduser("~")
VMTOOL_DIR = os.path.join(USER_HOME, "VideoMixTool")
LOGS_DIR = os.path.join(VMTOOL_DIR, "logs")
CONFIG_DIR = os.path.join(VMTOOL_DIR, "config")
GPU_CONFIG_PATH = os.path.join(VMTOOL_DIR, "gpu_config.json")
CACHE_DIR = os.path.join(VMTOOL_DIR, "cache")

# 确保目录存在
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

def check_ffmpeg():
    """检查FFmpeg是否可用，并返回其路径"""
    ffmpeg_path = None
    
    # 首先检查当前目录下是否有ffmpeg_path.txt
    if os.path.exists("ffmpeg_path.txt"):
        with open("ffmpeg_path.txt", "r", encoding="utf-8") as f:
            ffmpeg_path = f.read().strip()
            if ffmpeg_path and os.path.exists(ffmpeg_path):
                print(f"找到自定义FFmpeg路径: {ffmpeg_path}")
                return ffmpeg_path
    
    # 检查是否有ffmpeg子目录
    potential_paths = [
        os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(os.getcwd(), "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe"),
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            print(f"找到FFmpeg路径: {path}")
            return path
    
    # 检查环境变量
    try:
        result = subprocess.run(
            ["where", "ffmpeg"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        if result.returncode == 0:
            ffmpeg_path = result.stdout.strip().split("\n")[0]
            print(f"在系统路径中找到FFmpeg: {ffmpeg_path}")
            return ffmpeg_path
    except Exception as e:
        print(f"检查系统路径中的FFmpeg时出错: {str(e)}")
    
    # 如果找不到，提示用户
    print("警告: 未找到FFmpeg。请确保已正确安装FFmpeg或在ffmpeg_path.txt中指定路径")
    return None

def fix_gpu_config():
    """修复GPU配置文件"""
    gpu_config = {
        "use_hardware_acceleration": True,
        "encoder": "h264_nvenc",
        "decoder": "h264_cuvid",
        "encoding_preset": "medium",  # 使用更兼容的预设
        "extra_params": {
            "b:v": "5000k",
            "maxrate": "7500k",
            "bufsize": "10000k",
            "rc:v": "vbr_hq",
            "cq:v": "19",
            "qmin": "0", 
            "qmax": "51"
        },
        "detected_gpu": "NVIDIA GPU",
        "detected_vendor": "NVIDIA",
        "compatibility_mode": True,  # 启用兼容模式
        "driver_version": "unknown"
    }
    
    # 检查是否有NVIDIA GPU
    has_nvidia = False
    try:
        # 尝试运行nvidia-smi
        result = subprocess.run(
            ["nvidia-smi"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        has_nvidia = result.returncode == 0
    except:
        pass
    
    if not has_nvidia:
        # 如果没有NVIDIA GPU，则使用CPU配置
        gpu_config = {
            "use_hardware_acceleration": False,
            "encoder": "libx264",
            "encoding_preset": "medium",
            "extra_params": {
                "crf": "23"
            },
            "compatibility_mode": False
        }
        print("未检测到NVIDIA GPU，将使用CPU编码")
    else:
        print("检测到NVIDIA GPU，将使用硬件加速编码")
    
    # 保存GPU配置
    with open(GPU_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(gpu_config, f, ensure_ascii=False, indent=2)
    
    print(f"GPU配置已更新: {GPU_CONFIG_PATH}")
    return has_nvidia

def fix_output_permissions():
    """修复输出目录权限问题"""
    # 检查用户桌面目录权限
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.exists(desktop_path):
        test_file_path = os.path.join(desktop_path, "test_write_permission.txt")
        try:
            with open(test_file_path, "w") as f:
                f.write("测试写入权限")
            os.remove(test_file_path)
            print(f"桌面目录权限正常: {desktop_path}")
        except Exception as e:
            print(f"警告: 桌面目录权限不足，可能影响视频导出: {str(e)}")
    
    # 检查缓存目录权限
    try:
        test_file_path = os.path.join(CACHE_DIR, "test_write_permission.txt")
        with open(test_file_path, "w") as f:
            f.write("测试写入权限")
        os.remove(test_file_path)
        print(f"缓存目录权限正常: {CACHE_DIR}")
    except Exception as e:
        print(f"警告: 缓存目录权限不足，可能影响视频处理: {str(e)}")
        try:
            # 尝试修复缓存目录权限
            os.makedirs(CACHE_DIR, exist_ok=True)
            print(f"已尝试重新创建缓存目录: {CACHE_DIR}")
        except:
            pass

def fix_video_processor():
    """修复视频处理器核心逻辑"""
    # 查找主要代码文件位置
    video_processor_paths = [
        os.path.join("src", "core", "video_processor.py"),
        os.path.join(os.getcwd(), "src", "core", "video_processor.py"),
    ]
    
    video_processor_path = None
    for path in video_processor_paths:
        if os.path.exists(path):
            video_processor_path = path
            break
    
    if not video_processor_path:
        print("无法找到视频处理器代码文件，跳过代码修复")
        return
    
    print(f"正在修复视频处理器代码: {video_processor_path}")
    
    # 备份文件
    backup_path = f"{video_processor_path}.bak"
    try:
        shutil.copy2(video_processor_path, backup_path)
        print(f"已创建备份: {backup_path}")
    except Exception as e:
        print(f"创建备份时出错: {str(e)}")
        return
    
    # 读取文件内容
    try:
        with open(video_processor_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        # 如果UTF-8解码失败，尝试其他编码
        try:
            with open(video_processor_path, "r", encoding="gbk") as f:
                content = f.read()
        except:
            print(f"读取视频处理器代码文件失败，无法修复")
            return
    
    # 修改内容
    # 1. 修复空素材检测问题
    if "场景 '{folder_name}' 没有可用视频，跳过" in content:
        old_code = "if not videos:\n            logger.warning(f\"场景 '{folder_name}' 没有可用视频，跳过\")\n            continue"
        new_code = """if not videos:
            logger.error(f"场景 '{folder_name}' 没有可用视频，无法生成视频")
            # 提前返回错误消息，避免生成无效的1秒视频
            self.report_progress(f"错误: 场景 '{folder_name}' 没有可用视频", 100)
            raise ValueError(f"场景 '{folder_name}' 没有可用视频，无法生成视频")"""
        content = content.replace(old_code, new_code)
        print("已修复空素材检测问题")
    
    # 2. 修复配音时长裁剪问题
    if "根据配音时长裁剪视频" in content and "video_clip = video_clip.subclip" in content:
        # 查找相关代码段的位置
        start_idx = content.find("# 根据配音时长裁剪视频")
        if start_idx > 0:
            # 定位到包含 video_clip = video_clip.subclip 的行
            subclip_idx = content.find("video_clip = video_clip.subclip", start_idx)
            if subclip_idx > 0:
                # 找到该行结束的位置
                line_end = content.find("\n", subclip_idx)
                if line_end > 0:
                    # 提取该行代码
                    subclip_line = content[subclip_idx:line_end]
                    # 替换裁剪逻辑，确保始终有视频片段
                    modified_subclip_line = subclip_line.replace("video_clip = video_clip.subclip", 
                                                              "video_clip = video_clip.subclip")
                    # 添加错误处理
                    new_subclip_code = f"""try:
                            {modified_subclip_line}
                            if video_clip.duration < 0.5:  # 如果裁剪后视频太短
                                logger.warning(f"裁剪后视频时长过短: {{video_clip.duration:.2f}}秒，使用原始视频")
                                video_clip = VideoFileClip(video_file)  # 重新加载原始视频
                        except Exception as e:
                            logger.error(f"裁剪视频时出错: {{str(e)}}，使用原始视频")
                            video_clip = VideoFileClip(video_file)  # 使用原始视频"""
                    content = content.replace(subclip_line, new_subclip_code)
                    print("已修复视频裁剪问题")
    
    # 3. 增强输出路径处理
    if "处理output_path，确保使用短路径名" in content:
        # 找到这段代码的开始位置
        start_idx = content.find("# 处理output_path，确保使用短路径名")
        if start_idx > 0:
            # 找到这段代码的结束位置 (下一个 try 或 if 或函数)
            next_segment = min([pos for pos in [
                content.find("\n        try:", start_idx + 1),
                content.find("\n        if ", start_idx + 1),
                content.find("\n    def ", start_idx + 1)
            ] if pos > 0])
            
            if next_segment > 0:
                # 提取整段代码
                output_path_code = content[start_idx:next_segment]
                # 创建改进的输出路径处理代码
                improved_code = """# 处理output_path，确保使用短路径名并提前检查输出目录
        original_output_path = output_path
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            try:
                logger.info(f"创建输出目录: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"创建输出目录失败: {str(e)}")
                raise ValueError(f"无法创建输出目录: {output_dir}, 错误: {str(e)}")
        
        # 测试输出目录写入权限
        try:
            test_file = os.path.join(output_dir, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"输出目录权限检查通过: {output_dir}")
        except Exception as e:
            logger.error(f"输出目录写入权限检查失败: {str(e)}")
            raise ValueError(f"无法写入输出目录: {output_dir}, 请检查权限或使用其他目录")
        
        # 转换为短路径（仅Windows）
        if os.name == 'nt':
            try:
                import win32api
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
                output_path = original_output_path"""
                
                # 替换代码
                content = content.replace(output_path_code, improved_code)
                print("已增强输出路径处理")
    
    # 4. 增强合成检查
    if "merge_clips_with_transitions" in content and "# 合并所有剪辑" in content:
        merge_idx = content.find("def _merge_clips_with_transitions")
        if merge_idx > 0:
            # 找到函数体开始的位置
            func_body_start = content.find(":", merge_idx)
            if func_body_start > 0:
                # 在函数体开始处插入错误检查代码
                check_code = """
        # 增强合成前检查
        if not clip_infos:
            logger.error("没有可用的剪辑信息，无法合成视频")
            raise ValueError("没有可用的剪辑信息，无法合成视频")
        
        # 确保所有剪辑对象有效
        for i, info in enumerate(clip_infos):
            if not info.get("clip"):
                logger.error(f"第{i+1}个剪辑对象无效")
                raise ValueError(f"第{i+1}个剪辑对象无效")
            
            clip = info.get("clip")
            if clip.duration < 0.5:  # 如果剪辑太短
                logger.error(f"第{i+1}个剪辑时长过短: {clip.duration:.2f}秒")
                raise ValueError(f"剪辑时长过短: {clip.duration:.2f}秒，最小需要0.5秒")
                """
                
                # 找到第一行缩进代码
                first_line_idx = content.find("\n        ", func_body_start)
                if first_line_idx > 0:
                    # 插入检查代码
                    content = content[:first_line_idx] + check_code + content[first_line_idx:]
                    print("已增强合成前检查")
    
    # 保存修改后的内容
    try:
        with open(video_processor_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"视频处理器代码修复完成: {video_processor_path}")
    except Exception as e:
        print(f"保存修改后的代码时出错: {str(e)}")
        try:
            # 尝试恢复备份
            shutil.copy2(backup_path, video_processor_path)
            print(f"已恢复备份: {video_processor_path}")
        except:
            pass

def create_test_video():
    """创建测试视频，用于验证编码功能"""
    ffmpeg_path = check_ffmpeg()
    if not ffmpeg_path:
        print("无法创建测试视频: FFmpeg不可用")
        return
    
    test_output = os.path.join(os.getcwd(), "test_output.mp4")
    
    # 创建一个简单的测试视频 (彩色条纹，3秒)
    try:
        cmd = [
            ffmpeg_path,
            "-f", "lavfi",
            "-i", "testsrc=duration=3:size=1280x720:rate=30",
            "-c:v", "libx264",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-y",
            test_output
        ]
        
        print(f"正在创建测试视频: {test_output}")
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            print(f"测试视频创建成功: {test_output}")
            print(f"文件大小: {os.path.getsize(test_output) / 1024:.1f} KB")
            return test_output
        else:
            print(f"创建测试视频失败: {process.stderr}")
    except Exception as e:
        print(f"创建测试视频时出错: {str(e)}")
    
    return None

def test_gpu_encoding(test_video_path):
    """测试GPU编码功能"""
    if not test_video_path or not os.path.exists(test_video_path):
        print("无法测试GPU编码: 测试视频不存在")
        return False
    
    ffmpeg_path = check_ffmpeg()
    if not ffmpeg_path:
        print("无法测试GPU编码: FFmpeg不可用")
        return False
    
    # 测试NVIDIA GPU编码
    test_output = os.path.join(os.getcwd(), "test_output_gpu.mp4")
    
    try:
        cmd = [
            ffmpeg_path,
            "-i", test_video_path,
            "-c:v", "h264_nvenc",
            "-preset", "medium",
            "-b:v", "5000k",
            "-y",
            test_output
        ]
        
        print(f"正在测试NVIDIA GPU编码: {test_output}")
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            print(f"GPU编码测试成功: {test_output}")
            print(f"文件大小: {os.path.getsize(test_output) / 1024:.1f} KB")
            return True
        else:
            print(f"GPU编码测试失败: {process.stderr}")
            # 尝试使用兼容性参数
            cmd = [
                ffmpeg_path,
                "-i", test_video_path,
                "-c:v", "h264_nvenc",
                "-preset", "p7", # 更兼容的预设
                "-b:v", "5000k",
                "-y",
                test_output
            ]
            
            print("正在使用兼容性参数重试GPU编码...")
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode == 0:
                print(f"兼容模式GPU编码测试成功: {test_output}")
                print(f"文件大小: {os.path.getsize(test_output) / 1024:.1f} KB")
                return True
            else:
                print(f"兼容模式GPU编码测试失败: {process.stderr}")
    except Exception as e:
        print(f"测试GPU编码时出错: {str(e)}")
    
    return False

def fix_encoding_mode():
    """修复编码模式设置"""
    # 尝试创建一个.txt文件，提示用户切换到标准模式
    help_file = os.path.join(os.getcwd(), "视频合成问题修复说明.txt")
    
    content = """视频合成问题修复说明

如果您在使用视频混剪工具时，遇到视频合成只有1秒钟的问题，请尝试以下步骤：

1. 在视频混剪工具中，切换到"标准模式(重编码)"而非"快速模式(不重编码)"
   - 在合成设置界面，将"视频模式"设置为"标准模式"
   - 如果找不到此设置，请在合成参数中选择"标准质量模式"

2. 确保输出目录有足够的权限和空间
   - 尝试更改为桌面或文档等简单路径
   - 确保磁盘有足够空间(至少5GB可用空间)

3. 检查素材文件
   - 确保素材文件夹中包含有效的视频和配音文件
   - 视频和配音文件应分别放在"视频"和"配音"子文件夹中

4. 如果上述方法无效，可以尝试关闭GPU加速
   - 在设置中暂时禁用硬件加速功能
   - 软件将使用CPU进行编码(较慢但更稳定)

5. 重启软件后再试

如果问题仍然存在，请联系技术支持并提供以下信息：
- 日志文件(位于 %UserProfile%\\VideoMixTool\\logs 目录)
- 素材文件夹结构截图
- 详细的错误信息

本文件由视频合成修复工具自动生成
"""
    
    try:
        with open(help_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"已创建合成问题修复说明: {help_file}")
    except Exception as e:
        print(f"创建修复说明文件时出错: {str(e)}")

def main():
    """主函数"""
    print("=" * 60)
    print("视频合成失败修复工具")
    print("用于修复视频混剪工具中合成过程只有1秒钟的问题")
    print("=" * 60)
    
    # 步骤1: 检查FFmpeg
    print("\n[步骤1] 检查FFmpeg...")
    ffmpeg_path = check_ffmpeg()
    
    if not ffmpeg_path:
        print("警告: 未检测到有效的FFmpeg，这可能影响视频合成")
    
    # 步骤2: 修复GPU配置
    print("\n[步骤2] 修复GPU配置...")
    has_nvidia = fix_gpu_config()
    
    # 步骤3: 检查并修复输出权限问题
    print("\n[步骤3] 检查输出权限...")
    fix_output_permissions()
    
    # 步骤4: 修复视频处理器逻辑
    print("\n[步骤4] 修复视频处理器...")
    fix_video_processor()
    
    # 步骤5: 创建测试视频
    print("\n[步骤5] 创建测试视频...")
    test_video_path = create_test_video()
    
    # 步骤6: 测试GPU编码
    gpu_encoding_ok = False
    if has_nvidia and test_video_path:
        print("\n[步骤6] 测试GPU编码...")
        gpu_encoding_ok = test_gpu_encoding(test_video_path)
    
    # 步骤7: 修复编码模式设置
    print("\n[步骤7] 生成修复建议...")
    fix_encoding_mode()
    
    # 完成
    print("\n" + "=" * 60)
    print("修复完成！")
    print("\n建议操作:")
    print("1. 重启视频混剪工具")
    if not gpu_encoding_ok and has_nvidia:
        print("2. 尝试在设置中关闭硬件加速，使用CPU编码")
    print("3. 在合成设置中选择'标准模式(重编码)'而非'快速模式'")
    print("4. 确保素材文件夹包含有效的视频和配音文件")
    print("5. 尝试更简单的输出路径(如桌面)")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
        print("\n按回车键退出...")
        input()
    except Exception as e:
        print(f"\n修复过程中出错: {str(e)}")
        print("\n按回车键退出...")
        input() 