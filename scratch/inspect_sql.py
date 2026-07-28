import difflib

path1 = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge\extracted_knowledge\database.sql"
path2 = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\database2.sql"

with open(path1, 'r', encoding='utf-8') as f1:
    lines1 = f1.readlines()

with open(path2, 'r', encoding='utf-8') as f2:
    lines2 = f2.readlines()

print(f"File 1 lines: {len(lines1)}, File 2 lines: {len(lines2)}")

diff = difflib.unified_diff(lines1, lines2, fromfile='database.sql', tofile='database2.sql', n=2)
diff_lines = list(diff)
print(f"Total diff lines: {len(diff_lines)}")

# Write diff to file
with open(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\scratch\db_diff.txt", "w", encoding="utf-8") as out:
    out.writelines(diff_lines[:1000]) # write first 1000 lines of diff

print("Diff written to scratch/db_diff.txt")
