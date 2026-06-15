import os
import shutil

src_git = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\scratch\temp_clone\.git"
dst_git = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\.git"

print(f"Moving .git from {src_git} to {dst_git}...")
if os.path.exists(dst_git):
    shutil.rmtree(dst_git)

shutil.copytree(src_git, dst_git)
print(".git directory moved successfully!")
