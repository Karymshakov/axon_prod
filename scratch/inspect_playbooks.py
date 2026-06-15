def parse_playbooks(sql_path):
    in_block = False
    rows = []
    with open(sql_path, 'r', encoding='utf-8') as f:
        for line in f:
            line_str = line.strip('\r\n')
            if line_str.startswith("COPY public.hotel_info_playbook "):
                in_block = True
                continue
            if in_block:
                if line_str == "\\.":
                    break
                rows.append(line_str)
    
    print(f"Total playbooks: {len(rows)}")
    for r in rows:
        parts = r.split('\t')
        print(f"ID: {parts[0]}, Name: {parts[1]}, Org ID: {parts[9] if len(parts) > 9 else 'N/A'}")

parse_playbooks(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\database2.sql")
