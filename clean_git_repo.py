import os
import shutil
import subprocess

def run_command(command):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(command, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}")
        print(f"错误输出: {e.stderr}")
        return None

def backup_important_files():
    """备份重要文件（非大型二进制文件）到backup目录"""
    if not os.path.exists('git_backup'):
        os.makedirs('git_backup')
    
    # 从.gitignore中读取要排除的模式
    ignore_patterns = []
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.append(line)
    
    # 复制所有非忽略的文件
    for root, dirs, files in os.walk('.', topdown=True):
        # 跳过.git和git_backup目录
        if '.git' in dirs:
            dirs.remove('.git')
        if 'git_backup' in dirs:
            dirs.remove('git_backup')
        if 'temp' in dirs:
            dirs.remove('temp')
        
        # 创建对应的目录结构
        rel_dir = os.path.relpath(root, '.')
        if rel_dir != '.':
            backup_dir = os.path.join('git_backup', rel_dir)
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
        else:
            backup_dir = 'git_backup'
        
        # 复制文件
        for file in files:
            # 跳过大型二进制文件和临时文件
            skip = False
            for pattern in ignore_patterns:
                if pattern.endswith('/'):
                    # 目录模式
                    if os.path.join(rel_dir, '').startswith(pattern):
                        skip = True
                        break
                elif '*' in pattern:
                    # 通配符模式 - 简单处理，实际应使用fnmatch或glob
                    ext = pattern.replace('*', '')
                    if file.endswith(ext):
                        skip = True
                        break
                elif file == pattern or os.path.join(rel_dir, file) == pattern:
                    skip = True
                    break
            
            if not skip and file != '.gitignore' and file != 'clean_git_repo.py':
                src = os.path.join(root, file)
                dst = os.path.join(backup_dir, file)
                try:
                    shutil.copy2(src, dst)
                    print(f"已备份: {src} -> {dst}")
                except (shutil.Error, IOError) as e:
                    print(f"无法备份 {src}: {e}")

def clean_git_repo():
    """清理Git仓库，移除所有历史中的大文件"""
    print("开始清理Git仓库...")
    
    # 确保.gitignore已设置
    if not os.path.exists('.gitignore'):
        print("错误: 未找到.gitignore文件")
        return False
    
    # 备份重要文件
    print("备份重要文件...")
    backup_important_files()
    
    # 重新初始化仓库
    print("重新初始化Git仓库...")
    if os.path.exists('.git'):
        shutil.rmtree('.git')
    
    run_command('git init')
    run_command('git add .')
    run_command('git commit -m "Initial commit with clean history"')
    
    print("\n清理完成! 所有重要文件已备份到 git_backup 目录。")
    print("现在您可以使用以下命令添加远程仓库并推送:")
    print("  git remote add origin <your-repo-url>")
    print("  git push -u origin master --force")
    
if __name__ == "__main__":
    clean_git_repo() 