import os
import filecmp

dir1 = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\scratch\temp_clone"
dir2 = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes"

diffs = []

def compare_dirs(d1, d2):
    for item in os.listdir(d1):
        if item in ('.git', '.venv', '.idea', 'node_modules', 'scratch', 'extracted_knowledge', 'extracted_knowledge2'):
            continue
        p1 = os.path.join(d1, item)
        p2 = os.path.join(d2, item)
        
        if os.path.isdir(p1):
            if not os.path.exists(p2):
                diffs.append(f"Directory only in clone: {os.path.relpath(p1, dir1)}")
            else:
                compare_dirs(p1, p2)
        else:
            if not os.path.exists(p2):
                diffs.append(f"File only in clone: {os.path.relpath(p1, dir1)}")
            elif not filecmp.cmp(p1, p2, shallow=False):
                diffs.append(f"File differs: {os.path.relpath(p1, dir1)}")

compare_dirs(dir1, dir2)

print(f"Total differences: {len(diffs)}")
for d in diffs[:50]:
    print(d)
