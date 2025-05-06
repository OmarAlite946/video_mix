import os
import shutil
from pathlib import Path

def move_git_with_link():
    """移动.git目录并创建链接"""
    # 1. 确保.git目录存在
    git_dir = Path(".git")
    if not git_dir.exists():
        print(".git目录不存在")
        return
    
    # 2. 创建目标目录
    target_dir = Path("D:/GitRepositories/视频混剪工具")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 3. 移动.git目录
        if (target_dir / ".git").exists():
            shutil.rmtree(target_dir / ".git")
        shutil.move(str(git_dir), str(target_dir / ".git"))
        
        # 4. 创建.git文件，指向新位置
        with open(".git", "w") as f:
            f.write(f"gitdir: {target_dir / '.git'}")
        
        print(f"已将.git目录移动到 {target_dir}")
        print("并创建了链接文件")
        
    except Exception as e:
        print(f"操作失败: {e}")

if __name__ == "__main__":
    print("开始移动.git目录并创建链接...")
    move_git_with_link()
    print("\n操作完成！") 