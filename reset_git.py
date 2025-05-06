import os
import shutil
import subprocess

def run_command(command):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(command, shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def reset_git_repo():
    """重置Git仓库，删除历史，重新初始化"""
    print("开始重置Git仓库...")
    
    # 获取当前分支名称
    current_branch = None
    try:
        result = subprocess.run('git branch --show-current', shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
        current_branch = result.stdout.strip()
        print(f"当前分支: {current_branch}")
    except:
        print("无法获取当前分支，将使用master作为默认分支")
        current_branch = "master"
    
    # 获取远程仓库URL
    remote_url = None
    try:
        result = subprocess.run('git remote get-url origin', shell=True, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
        remote_url = result.stdout.strip()
        print(f"远程仓库URL: {remote_url}")
    except:
        print("无法获取远程仓库URL")
        remote_url = None
    
    # 备份.gitignore
    has_gitignore = False
    if os.path.exists('.gitignore'):
        has_gitignore = True
        shutil.copy('.gitignore', '.gitignore_backup')
    
    # 删除Git管理信息
    print("移除Git管理...")
    
    # 检查.git是文件还是目录
    if os.path.isdir('.git'):
        # 是目录，直接删除
        shutil.rmtree('.git')
    elif os.path.isfile('.git'):
        # 是文件（可能是链接），读取内容
        git_link = None
        try:
            with open('.git', 'r') as f:
                content = f.read().strip()
                if content.startswith('gitdir:'):
                    git_link = content.split('gitdir:')[1].strip()
        except:
            pass
        
        # 删除.git文件
        os.remove('.git')
        
        # 如果找到了链接目标，而且目标存在，删除目标
        if git_link and os.path.exists(git_link) and os.path.isdir(git_link):
            print(f"删除链接的Git仓库: {git_link}")
            try:
                shutil.rmtree(git_link)
            except Exception as e:
                print(f"无法删除链接的Git仓库: {e}")
                print("这可能需要您手动删除")
    
    # 重新初始化仓库
    print("重新初始化Git仓库...")
    if not run_command('git init'):
        return False
    
    # 恢复.gitignore
    if has_gitignore:
        shutil.move('.gitignore_backup', '.gitignore')
    
    # 添加所有文件
    print("添加所有文件...")
    if not run_command('git add .'):
        return False
    
    # 提交
    print("提交文件...")
    if not run_command('git commit -m "Initial commit with clean history"'):
        return False
    
    # 重命名分支（如果需要）
    if current_branch and current_branch != "master":
        print(f"重命名分支为 {current_branch}...")
        if not run_command(f'git branch -M {current_branch}'):
            return False
    
    # 添加远程仓库
    if remote_url:
        print("添加远程仓库...")
        if not run_command(f'git remote add origin {remote_url}'):
            return False
    
    print("\nGit仓库已重置！")
    print("现在可以使用以下命令推送到远程仓库:")
    if remote_url:
        print(f"  git push -f origin {current_branch}")
    else:
        print("  git remote add origin <your-repo-url>")
        print(f"  git push -f origin {current_branch}")
    
    return True

if __name__ == "__main__":
    reset_git_repo() 