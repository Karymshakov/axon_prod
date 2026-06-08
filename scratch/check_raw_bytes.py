import os

log_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\logs\django.log"
with open(log_path, "rb") as f:
    content = f.read()

# Let's find the last 5000 bytes and print their characters and hex
last_bytes = content[-8000:]
try:
    print(last_bytes.decode('utf-8', errors='replace')[-2000:])
except Exception as e:
    print("Error decoding:", e)
