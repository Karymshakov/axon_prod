import os

filename1 = "DSC06522.jpg"
filename2 = "4M1A2140.jpg"
workspace = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes"

print("Scanning for media files...")
for root, dirs, files in os.walk(workspace):
    # skip .venv, .git, .idea, node_modules
    dirs[:] = [d for d in dirs if d not in ('.venv', '.git', '.idea', 'node_modules')]
    for file in files:
        if file in (filename1, filename2):
            print(os.path.join(root, file))
