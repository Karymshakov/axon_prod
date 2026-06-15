import os
import shutil

src_dir = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\initial_media"
dst_dir = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\media"

print(f"Copying from {src_dir} to {dst_dir}...")
if not os.path.exists(src_dir):
    print("Source directory does not exist!")
    exit(1)

# Copy recursively
shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
print("Media files copied successfully!")
