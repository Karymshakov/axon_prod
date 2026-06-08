import os

log_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\logs\django.log"
out_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\scratch\extracted_recent_logs.txt"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

recent_lines = []
for line in lines:
    if "2026-05-26 18:" in line:
        recent_lines.append(line)

with open(out_path, "w", encoding="utf-8") as out:
    out.writelines(recent_lines)

print(f"Extracted {len(recent_lines)} lines to {out_path}")
