import os

log_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\logs\django.log"

with open(log_path, "rb") as f:
    lines = f.readlines()

for idx in range(3940, min(3970, len(lines))):
    print(f"L{idx}: {repr(lines[idx])}")


