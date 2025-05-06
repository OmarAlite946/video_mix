import os
import shutil
from pathlib import Path

def move_git():
    """移动.git目录"""
    git_dir = Path(".git")
    if not git_dir.exists():
        print("git目录不存在")
        return
    
    target_dir = Path("D:/GitRepositories/视频混剪工具")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if (target_dir / ".git").exists():
            shutil.rmtree(target_dir / ".git")
        shutil.move(str(git_dir), str(target_dir / ".git"))
        print(f"已将.git目录移动到 {target_dir}")
    except Exception as e:
        print(f"移动.git目录失败: {e}")

def move_test_files():
    """移动测试相关文件"""
    test_dirs = [
        "test_mixed_mode",
        "test_lnk_diagnosis",
        "tests",
        "backup"
    ]
    
    target_dir = Path("D:/开发文件/视频混剪工具测试")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    for dir_name in test_dirs:
        src_dir = Path(dir_name)
        if src_dir.exists():
            try:
                dst_dir = target_dir / dir_name
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.move(str(src_dir), str(dst_dir))
                print(f"已将 {dir_name} 移动到 {target_dir}")
            except Exception as e:
                print(f"移动 {dir_name} 失败: {e}")

def move_temp():
    """移动temp目录"""
    temp_dir = Path("temp")
    if not temp_dir.exists():
        print("temp目录不存在")
        return
    
    target_dir = Path("D:/临时文件/视频混剪工具")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(temp_dir), str(target_dir))
        print(f"已将temp目录移动到 {target_dir}")
    except Exception as e:
        print(f"移动temp目录失败: {e}")

def move_temp_files():
    """移动临时文件和构建文件"""
    dirs_to_move = [
        "temp",
        "__pycache__",
        "dist",
        "build",
        "packages",
        "logs"
    ]
    
    target_dir = Path("D:/临时文件/视频混剪工具")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    for dir_name in dirs_to_move:
        src_dir = Path(dir_name)
        if src_dir.exists():
            try:
                dst_dir = target_dir / dir_name
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.move(str(src_dir), str(dst_dir))
                print(f"已将 {dir_name} 移动到 {target_dir}")
            except Exception as e:
                print(f"移动 {dir_name} 失败: {e}")

if __name__ == "__main__":
    print("开始移动文件...")
    
    print("\n1. 移动.git目录...")
    move_git()
    
    print("\n2. 移动测试相关文件...")
    move_test_files()
    
    print("\n3. 移动temp目录...")
    move_temp()
    
    print("\n4. 移动临时文件和构建文件...")
    move_temp_files()
    
    print("\n移动完成！") 