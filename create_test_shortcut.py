import os
import win32com.client

def create_shortcut(target_path, shortcut_path):
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = target_path
    shortcut.save()
    print(f"创建快捷方式: {shortcut_path} -> {target_path}")

# 创建目标目录的完整路径
target_dir = os.path.abspath("test_lnk_diagnosis/target_folder")
parent_dir = os.path.abspath("test_lnk_diagnosis")

# 确保目标目录存在
if not os.path.exists(target_dir):
    print(f"目标目录不存在: {target_dir}")
    exit(1)

# 创建快捷方式
shortcut_path = os.path.join(parent_dir, "target_folder.lnk")
create_shortcut(target_dir, shortcut_path)

# 创建一个空文本文件作为测试素材
video_dir = os.path.join(target_dir, "视频")
if not os.path.exists(video_dir):
    os.makedirs(video_dir)

test_file = os.path.join(video_dir, "test.mp4")
with open(test_file, "w") as f:
    f.write("This is a test file")

print(f"创建测试文件: {test_file}")
print("测试环境准备完成") 