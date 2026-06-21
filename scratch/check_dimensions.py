import os
from PIL import Image

brain_dir = r"C:\Users\kille\.gemini\antigravity-ide\brain\038af392-e861-4635-a8ea-f0505fd421c1"
files = [
    "media__1782054631555.jpg",
    "media__1782054631599.jpg",
    "media__1782054631655.jpg",
    "media__1782054631685.jpg",
    "media__1782054631699.jpg",
    "media__1782055205355.png"
]

for filename in files:
    filepath = os.path.join(brain_dir, filename)
    if os.path.exists(filepath):
        try:
            with Image.open(filepath) as img:
                print(f"File={filename}, Format={img.format}, Size={img.size}, Mode={img.mode}")
        except Exception as exc:
            print(f"File={filename}, Error: {exc}")
    else:
        print(f"File={filename} does not exist")
