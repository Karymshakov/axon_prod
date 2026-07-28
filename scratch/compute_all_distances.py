import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres:admin@localhost:5432/app_dev"
django.setup()

from apps.hotel_media.fingerprints import compute_image_fingerprints, hamming_distance

brain_dir = r"C:\Users\kille\.gemini\antigravity-ide\brain\038af392-e861-4635-a8ea-f0505fd421c1"
files = [
    "media__1782054631555.jpg",
    "media__1782054631599.jpg",
    "media__1782054631655.jpg",
    "media__1782054631685.jpg",
    "media__1782054631699.jpg",
]

# Calculate fingerprints for each
fingerprints = {}
for filename in files:
    filepath = os.path.join(brain_dir, filename)
    if os.path.exists(filepath):
        try:
            fingerprints[filename] = compute_image_fingerprints(filepath, include_screenshot_regions=True)
        except Exception as exc:
            print(f"Error computing fingerprints for {filename}: {exc}")

# Compare pairs
for i in range(len(files)):
    for j in range(i + 1, len(files)):
        f1_name = files[i]
        f2_name = files[j]
        if f1_name not in fingerprints or f2_name not in fingerprints:
            continue
        
        # Find closest match between any region of f1 and any region of f2
        best_match = None
        for r1 in fingerprints[f1_name]:
            for r2 in fingerprints[f2_name]:
                if r1['hash_kind'] == r2['hash_kind'] and r1.get('bit_length') == r2.get('bit_length'):
                    dist = hamming_distance(r1['hash_value'], r2['hash_value'])
                    score = 1 - (dist / r1.get('bit_length', 64))
                    if best_match is None or dist < best_match['dist']:
                        best_match = {
                            'dist': dist,
                            'score': score,
                            'kind': r1['hash_kind'],
                            'r1_label': r1.get('crop_label', 'full'),
                            'r2_label': r2.get('crop_label', 'full')
                        }
        if best_match:
            print(f"{f1_name} vs {f2_name}: Min distance = {best_match['dist']} ({best_match['kind']}, score={best_match['score']:.3f}, {best_match['r1_label']} vs {best_match['r2_label']})")
