import os
import sys
import subprocess
import re
import urllib.parse
import json
import uuid
import psycopg

def main():
    # 1. Read DATABASE_URL from .env
    env_vars = {}
    env_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\.env"
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    db_url = env_vars.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env!")
        sys.exit(1)

    print("DATABASE_URL:", db_url)

    # 2. Re-create public schema in PostgreSQL
    print("Connecting to DB to reset public schema...")
    try:
        conn = psycopg.connect(db_url, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
            cur.execute("CREATE SCHEMA public;")
            cur.execute("GRANT ALL ON SCHEMA public TO public;")
        conn.close()
        print("Schema reset successful!")
    except Exception as e:
        print("Failed to reset schema:", e)
        sys.exit(1)

    # 3. Import database2.sql using psql.exe
    psql_path = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
    db2_sql_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\database2.sql"

    parsed = urllib.parse.urlparse(db_url)
    db_user = parsed.username
    db_password = parsed.password
    db_host = parsed.hostname
    db_port = parsed.port or 5432
    db_name = parsed.path.lstrip('/')

    print(f"Importing database2.sql into {db_name}...")
    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    cmd = [
        psql_path,
        "-h", db_host,
        "-p", str(db_port),
        "-U", db_user,
        "-d", db_name,
        "-f", db2_sql_path
    ]

    res = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if res.returncode != 0:
        print("Failed to import database!")
        print("psql Error Output:", res.stderr)
        sys.exit(1)
    else:
        print("Database imported successfully!")

    # 4. Bootstrap Django
    sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from apps.organizations.models import Organization, OrganizationMember
    from apps.flows.models import ConversationFlow, AgentConfig
    from apps.leads.models import AIConfig
    from apps.hotel_info.models import Playbook

    # 5. Run migrations
    print("Running Django migrations to bring database up to date...")
    try:
        subprocess.run([
            r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\.venv\Scripts\python.exe",
            r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend\manage.py",
            "migrate"
        ], check=True)
        print("Migrations applied successfully!")
    except Exception as e:
        print("Failed to run migrations:", e)
        sys.exit(1)

    # 6. Verify and create/update users
    print("Synchronizing users...")
    User = get_user_model()
    org1 = Organization.objects.get(id=1)

    target_users = [
        {"email": "admin@example.com", "name": "", "role": "admin", "is_superuser": True, "is_staff": True},
        {"email": "maksat@axondigital.com", "name": "Maksat", "role": "admin", "is_superuser": False, "is_staff": True},
        {"email": "erdem@axondigital.com", "name": "Erdem", "role": "admin", "is_superuser": False, "is_staff": True},
        {"email": "dastanbekovaitmyrza@gmail.com", "name": "Aitmyrza", "role": "support", "is_superuser": False, "is_staff": False},
        {"email": "admin@example1.com", "name": "admin", "role": "support", "is_superuser": False, "is_staff": False},
        {"email": "admin-toggle-test@example.com", "name": "Admin Toggle Test", "role": "admin", "is_superuser": False, "is_staff": True},
        {"email": "owner-toggle-test@example.com", "name": "Owner Toggle Test", "role": "admin", "is_superuser": False, "is_staff": True},
    ]

    for u_info in target_users:
        user, created = User.objects.get_or_create(email=u_info["email"])
        user.name = u_info["name"]
        user.role = u_info["role"]
        user.is_superuser = u_info["is_superuser"]
        user.is_staff = u_info["is_staff"]
        user.is_active = True
        user.current_organization = org1
        user.set_password("admin")
        user.save()
        print(f"User {u_info['email']} {'created' if created else 'updated'}")

        # membership
        member, created_member = OrganizationMember.objects.get_or_create(
            organization=org1,
            user=user,
            defaults={"role": OrganizationMember.Role.ADMIN if u_info["role"] == "admin" else OrganizationMember.Role.MEMBER}
        )
        if not created_member:
            member.role = OrganizationMember.Role.ADMIN if u_info["role"] == "admin" else OrganizationMember.Role.MEMBER
            member.save()

    # 7. Create Organizations 4 & 5 if they don't exist
    print("Synchronizing organizations...")
    admin_user = User.objects.get(email="admin@example.com")
    org4, created_org4 = Organization.objects.get_or_create(
        id=4,
        defaults={
            "name": "Nomad Camp 4",
            "slug": "nomad-camp-4",
            "owner": admin_user,
            "plan": Organization.Plan.FREE,
            "is_active": True,
        }
    )
    print(f"Organization 4 {'created' if created_org4 else 'already exists'}")

    org5, created_org5 = Organization.objects.get_or_create(
        id=5,
        defaults={
            "name": "Nomad Camp 5",
            "slug": "nomad-camp-5",
            "owner": admin_user,
            "plan": Organization.Plan.FREE,
            "is_active": True,
        }
    )
    print(f"Organization 5 {'created' if created_org5 else 'already exists'}")

    # 8. AI Config sync (leads.aiconfig) for Org 4 & 5
    print("Parsing and loading assistant configs for Org 4 & 5...")
    def parse_assistant_config(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        config = {}
        
        auto_response_match = re.search(r"\*\*Auto Response:\*\*\s*(True|False)", content)
        if auto_response_match:
            config["ai_auto_response"] = auto_response_match.group(1) == "True"
            
        auto_extract_match = re.search(r"\*\*Auto Extract Data:\*\*\s*(True|False)", content)
        if auto_extract_match:
            config["auto_extract_data"] = auto_extract_match.group(1) == "True"
            
        delay_match = re.search(r"\*\*Response Delay \(sec\):\*\*\s*(\d+)", content)
        if delay_match:
            config["response_delay"] = int(delay_match.group(1))
            
        prompt_match = re.search(r"## System Prompt\s*\n```text\n(.*?)\n```", content, re.DOTALL)
        if prompt_match:
            config["system_prompt"] = prompt_match.group(1)
            
        profile_match = re.search(r"## Company Profile\s*\n(.*)", content, re.DOTALL)
        if profile_match:
            config["company_profile"] = profile_match.group(1).strip()
            
        return config

    cfg4_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\prompts\aida_assistant_org4.md"
    cfg4_data = parse_assistant_config(cfg4_path)
    cfg4, created_cfg4 = AIConfig.objects.get_or_create(
        organization=org4,
        defaults=cfg4_data
    )
    if not created_cfg4:
        for k, v in cfg4_data.items():
            setattr(cfg4, k, v)
        cfg4.save()
    print("AIConfig for Org 4 loaded.")

    cfg5_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\prompts\aida_assistant_org5.md"
    cfg5_data = parse_assistant_config(cfg5_path)
    cfg5, created_cfg5 = AIConfig.objects.get_or_create(
        organization=org5,
        defaults=cfg5_data
    )
    if not created_cfg5:
        for k, v in cfg5_data.items():
            setattr(cfg5, k, v)
        cfg5.save()
    print("AIConfig for Org 5 loaded.")

    # 9. Agent prompts sync (flows.agentconfig) for Org 1
    print("Synchronizing agent prompts for Org 1...")
    def parse_agent_prompt(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split("---", 1)
        if len(parts) == 2:
            return parts[1].strip()
        return content.strip()

    agent_files = {
        "booking": "booking_agent.md",
        "consultant": "consultant_agent.md",
        "cs": "cs_agent.md",
        "router": "router_agent.md"
    }

    for name, filename in agent_files.items():
        file_path = os.path.join(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\prompts", filename)
        prompt_text = parse_agent_prompt(file_path)
        
        try:
            agent_cfg = AgentConfig.objects.get(name=name, organization=org1)
            agent_cfg.system_prompt = prompt_text
            agent_cfg.save()
            print(f"Updated AgentConfig: {name}")
        except AgentConfig.DoesNotExist:
            print(f"AgentConfig {name} not found for Org 1!")

    # 10. ConversationFlow global prompt sync (flows.conversationflow)
    print("Restoring global flow prompt from DB 1...")
    def parse_global_prompt(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"### Global Flow Prompt\s*\n```text\n(.*?)\n```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    global_prompt_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge\extracted_knowledge\conversation_flow.md"
    global_prompt_text = parse_global_prompt(global_prompt_path)

    try:
        flow = ConversationFlow.objects.get(id=1)
        flow.global_prompt = global_prompt_text
        flow.save()
        print("Updated ConversationFlow global_prompt successfully!")
    except ConversationFlow.DoesNotExist:
        print("ConversationFlow ID 1 not found!")

    # 11. Nomad Run Camp playbook loading (hotel_info.playbook) for Org 1
    print("Loading Nomad Run Camp playbook...")
    def parse_playbook_md(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        title_match = re.search(r"^# Playbook:\s*(.*)", content)
        playbook_name = title_match.group(1).strip() if title_match else "Playbook"
        
        trigger_match = re.search(r"\*\*Trigger Context:\*\*\s*(.*)", content)
        trigger_desc = trigger_match.group(1).strip() if trigger_match else ""
        
        inst_match = re.search(r"\*\*Instructions:\*\*\s*\n(.*?)\n---", content, re.DOTALL)
        instructions = inst_match.group(1).strip() if inst_match else ""
        
        sections_text = content.split("---", 1)[1] if "---" in content else content
        
        sections = []
        current_section = None
        
        lines = sections_text.split("\n")
        for line in lines:
            if line.startswith("## "):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "id": str(uuid.uuid4())[:12].replace("-", ""),
                    "title": line[3:].strip(),
                    "content": ""
                }
            elif current_section:
                current_section["content"] += line + "\n"
                
        if current_section:
            sections.append(current_section)
            
        for s in sections:
            s["content"] = s["content"].strip()
            
        return {
            "name": playbook_name,
            "trigger_description": trigger_desc,
            "instructions": instructions,
            "content": json.dumps(sections, ensure_ascii=False)
        }

    run_camp_pb_path = r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\extracted_knowledge2\extracted_knowledge2\playbooks\nomad_run_camp.md"
    pb_data = parse_playbook_md(run_camp_pb_path)

    pb, created_pb = Playbook.objects.get_or_create(
        name=pb_data["name"],
        organization=org1,
        defaults={
            "trigger_description": pb_data["trigger_description"],
            "instructions": pb_data["instructions"],
            "content": pb_data["content"],
            "is_active": True,
            "order": 13,
        }
    )
    if not created_pb:
        pb.trigger_description = pb_data["trigger_description"]
        pb.instructions = pb_data["instructions"]
        pb.content = pb_data["content"]
        pb.save()
        print("Updated Nomad Run Camp playbook.")
    else:
        print("Created Nomad Run Camp playbook.")

    print("\nDATABASE RESTORE AND CONFIG SYNC COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
