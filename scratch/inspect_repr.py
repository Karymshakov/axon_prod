import os

log_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\logs\django.log"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

for line in lines:
    if "2026-05-26 18:" in line:
        if "Received Telegram message from lead 1:" in line:
            print("GUEST MSG:", repr(line))
        elif "final AI text response:" in line:
            print("AI RESP:", repr(line))
        elif "AI called tool=" in line:
            print("TOOL CALL:", repr(line))
        elif "Advanced conversation summary" in line or "Updated conversation summary for lead 1:" in line:
            print("SUMMARY:", repr(line))
