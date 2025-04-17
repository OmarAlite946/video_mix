import os
import shutil
import win32com.client

def create_shortcut(target_path, shortcut_path):
    # 确保使用绝对路径
    abs_target_path = os.path.abspath(target_path)
    
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = abs_target_path
    shortcut.save()
    print(f"创建快捷方式: {shortcut_path} -> {abs_target_path}")

# 创建测试目录结构
test_dir = "test_mixed_mode"
if not os.path.exists(test_dir):
    os.makedirs(test_dir)
else:
    # 清空目录
    shutil.rmtree(test_dir)
    os.makedirs(test_dir)

print(f"创建测试目录: {test_dir}")

# 创建几个普通素材文件夹
for i in range(1, 4):
    folder_name = f"实体素材{i}"
    folder_path = os.path.join(test_dir, folder_name)
    
    # 创建素材文件夹结构
    video_dir = os.path.join(folder_path, "视频")
    audio_dir = os.path.join(folder_path, "配音")
    
    os.makedirs(video_dir)
    os.makedirs(audio_dir)
    
    # 创建测试文件
    video_file = os.path.join(video_dir, f"test_video{i}.mp4")
    audio_file = os.path.join(audio_dir, f"test_audio{i}.mp3")
    
    with open(video_file, "w") as f:
        f.write(f"This is test video {i}")
    
    with open(audio_file, "w") as f:
        f.write(f"This is test audio {i}")
    
    print(f"创建实体素材文件夹: {folder_path}")

# 创建一个目标文件夹用于快捷方式
targets_dir = os.path.join(test_dir, "targets")
os.makedirs(targets_dir)

# 创建目标素材
for i in range(4, 7):
    folder_name = f"目标素材{i}"
    folder_path = os.path.join(targets_dir, folder_name)
    
    # 创建素材文件夹结构
    video_dir = os.path.join(folder_path, "视频")
    audio_dir = os.path.join(folder_path, "配音")
    
    os.makedirs(video_dir)
    os.makedirs(audio_dir)
    
    # 创建测试文件
    video_file = os.path.join(video_dir, f"test_video{i}.mp4")
    audio_file = os.path.join(audio_dir, f"test_audio{i}.mp3")
    
    with open(video_file, "w") as f:
        f.write(f"This is test video {i}")
    
    with open(audio_file, "w") as f:
        f.write(f"This is test audio {i}")
    
    print(f"创建目标素材文件夹: {folder_path}")
    
    # 创建指向该文件夹的快捷方式
    shortcut_path = os.path.join(test_dir, f"{folder_name}.lnk")
    create_shortcut(folder_path, shortcut_path)

print("测试环境准备完成") 