import urllib.request

urls = [
    "http://localhost:8000/media/hotel_media/DSC06522.jpg",
    "http://localhost:8000/media/hotel_media/4M1A2140.jpg"
]

for url in urls:
    try:
        response = urllib.request.urlopen(url, timeout=3)
        print(f"URL: {url} - Status: {response.status}")
    except Exception as e:
        print(f"URL: {url} - Failed: {e}")
