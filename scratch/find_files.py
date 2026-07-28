import os

workspace = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes"
print("Scanning workspace for zip, sql, and backup files...")
for root, dirs, files in os.walk(workspace):
    # skip node_modules, .venv, .idea, .git
    dirs[:] = [d for d in dirs if d not in ('node_modules', '.venv', '.idea', '.git')]
    for file in files:
        if file.endswith(('.sql', '.zip', '.tar', '.gz', '.backup')):
            print(os.path.join(root, file))
