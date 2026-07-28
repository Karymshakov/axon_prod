import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.flows.models import AIModelConfig

cfg = AIModelConfig.objects.first()
if cfg:
    print("AIModelConfig found:")
    print("ID:", cfg.id)
    print("Temperature:", cfg.temperature)
    print("Max Tokens:", cfg.max_tokens)
else:
    print("AIModelConfig not found")
