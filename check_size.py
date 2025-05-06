import os
from pathlib import Path

def get_dir_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except:
                continue
    return total_size / (1024 * 1024 * 1024)  # 转换为GB

current_dir = Path.cwd()
print("正在检查目录大小...\n")

for item in current_dir.iterdir():
    if item.is_dir():
        try:
            size_gb = get_dir_size(item)
            if size_gb > 0.1:  # 只显示大于100MB的目录
                print(f"{item.name}: {size_gb:.2f} GB")
        except Exception as e:
            print(f"检查 {item.name} 时出错: {e}") 