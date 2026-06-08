import os

log_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\logs\django.log"
out_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\scratch\lead1_log.txt"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

lead1_lines = []
for line in lines:
    # Filter for logs of lead 1 from 18:10 onwards today
    if "2026-05-26 18:" in line and ("lead 1" in line or "lead=1" in line or "get_room_options" in line or "get_family_room" in line or "AI RESPONSE" in line):
        lead1_lines.append(line)

with open(out_path, "w", encoding="utf-8") as out:
    out.writelines(lead1_lines)

print(f"Extracted {len(lead1_lines)} lines to {out_path}")
