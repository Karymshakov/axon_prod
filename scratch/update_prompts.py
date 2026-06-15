import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.hotel_info.models import Playbook
from apps.flows.models import ConversationFlow, FlowCard
from apps.leads.models import AIConfig

# 1. Update AIConfig ID 1
try:
    conf = AIConfig.objects.get(id=1)
    system_prompt = conf.system_prompt
    if "CURRENCY RULE" not in system_prompt:
        system_prompt += (
            "\n\nCURRENCY RULE — CRITICAL:\n"
            "All prices are in Kyrgyz Soms (сом / сомов). ALWAYS use the currency \"сом\" or \"сомов\" when presenting prices to guests.\n"
            "STRICTLY FORBIDDEN: Do NOT use Rubles (рубль, рублей, ₽), Dollars ($), or any other currency under any circumstances."
        )
        conf.system_prompt = system_prompt
        conf.save()
        print("AIConfig ID 1 system prompt updated successfully.")
    else:
        print("AIConfig ID 1 system prompt already contains the currency rule.")
except AIConfig.DoesNotExist:
    print("AIConfig ID 1 not found.")

# 2. Update ConversationFlow ID 1
try:
    flow = ConversationFlow.objects.get(id=1)
    global_prompt = flow.global_prompt
    if "ВАЛЮТА" not in global_prompt:
        global_prompt += (
            "\n\nВАЛЮТА — КРИТИЧЕСКИ ВАЖНО:\n"
            "Все цены в системе указаны в кыргызских сомах (сом). При ответе гостю ВСЕГДА используй исключительно валюту \"сом\" (или \"сомов\"). Категорически запрещено использовать рубли, рублей, ₽, или любые другие валюты."
        )
        flow.global_prompt = global_prompt
        flow.save()
        print("ConversationFlow ID 1 global prompt updated successfully.")
    else:
        print("ConversationFlow ID 1 global prompt already contains the currency rule.")
except ConversationFlow.DoesNotExist:
    print("ConversationFlow ID 1 not found.")

# 3. Update Playbook 10
try:
    p10 = Playbook.objects.get(id=10)
    p10.instructions = (
        "Сначала задай два вопроса про даты и количество гостей.\n"
        "УМНАЯ ЛОГИКА ДЛЯ ДЕТЕЙ:\n"
        "Если гостей 3 или более человек, перед показом номеров обязательно уточни про детей:\n"
        "- Если вообще неизвестно, будут ли дети: остановись и спроси: «Будут ли с вами дети и какого они возраста?».\n"
        "- Если гость упомянул детей (например, \"1 ребенок\", \"с детьми\"), но еще НЕ известен их возраст: остановись и спроси: «Подскажите, пожалуйста, какого возраста дети?».\n"
        "- Если детей нет (только взрослые) или известны и дети, и их возраст — переходи к сбору остальных данных / предложению вариантов.\n"
        "Собери все данные для брони перед передачей менеджеру.\n"
        "После сбора данных — отправь шаблон подтверждения и сообщи, что менеджер пришлёт ваучер."
    )
    p10.save()
    print("Playbook 10 updated successfully.")
except Playbook.DoesNotExist:
    print("Playbook 10 not found.")

# 4. Update FlowCard 12
try:
    fc12 = FlowCard.objects.get(id=12)
    current_template = fc12.message_template
    
    idx = current_template.find("ИНСТРУМЕНТ — ОБЯЗАТЕЛЬНЫЙ ВЫЗОВ:")
    if idx != -1:
        rest = current_template[idx:]
    else:
        rest = current_template
        
    new_template = (
        "⚠️ КРИТИЧЕСКОЕ ИСКЛЮЧЕНИЕ ДЛЯ ВЫЗОВА ИНСТРУМЕНТА (ДЕТИ):\n"
        "Если общее количество гостей 3 или более человек (guest_count >= 3):\n"
        "1. ЗАПРЕЩЕНО вызывать get_room_options или get_family_room, пока не соберешь информацию о детях!\n"
        "2. Если в истории чата еще НЕ обсуждалось, будут ли дети:\n"
        "   Остановись и спроси: «Будут ли с вами дети и какого они возраста?».\n"
        "3. Если известно, что дети будут (например, гость написал \"1 ребенок\" или \"с детьми\"), но еще НЕ известен их возраст:\n"
        "   Остановись и спроси: «Подскажите, пожалуйста, какого возраста дети?».\n"
        "4. Если детей нет (только взрослые) → вызови get_room_options.\n"
        "5. Если известны и дети, и их возраст → вызови get_family_room.\n"
        "Не предлагай никаких вариантов размещения, пока не получишь эту информацию!\n\n"
        + rest
    )
    fc12.message_template = new_template
    fc12.save()
    print("FlowCard 12 updated successfully.")
except FlowCard.DoesNotExist:
    print("FlowCard 12 not found.")
