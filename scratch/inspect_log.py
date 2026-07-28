import os

log_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\logs\django.log"
if os.path.exists(log_path):
    print("File exists, size:", os.path.getsize(log_path))
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        print("Total lines:", len(lines))
        print("First 20 lines:")
        for line in lines[:20]:
            print(line.strip())
        print("Last 20 lines:")
        for line in lines[-20:]:
            print(line.strip())
else:
    print("File does not exist")
