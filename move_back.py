import os
import shutil
from pathlib import Path

def move_git_back():
    """把.git目录移回来"""
    source_dir = Path("D:/GitRepositories/视频混剪工具/.git")
    if not source_dir.exists():
        print("源目录不存在")
        return
    
    target_dir = Path.cwd()
    try:
        if (target_dir / ".git").exists():
            shutil.rmtree(target_dir / ".git")
        shutil.move(str(source_dir), str(target_dir / ".git"))
        print(f"已将.git目录移回 {target_dir}")
    except Exception as e:
        print(f"移动.git目录失败: {e}")

if __name__ == "__main__":
    print("开始移动.git目录...")
    move_git_back()
    print("\n移动完成！") 