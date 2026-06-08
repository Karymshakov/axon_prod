import os
import sys
import django

sys.path.append(r"c:\Users\User\PycharmProjects\cayu\nomw-my_changes\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.leads.models import Lead, LeadActivity
from apps.leads.ai_service import ai_service

lead = Lead.objects.get(id=5)

lead_data = {
    'contact_person': lead.contact_person,
    'source': lead.source,
    'phone': lead.phone,
    'email': lead.email,
    'check_in_date': str(lead.check_in_date) if lead.check_in_date else None,
    'check_out_date': str(lead.check_out_date) if lead.check_out_date else None,
    'guest_count': lead.guest_count,
    'room_type_preference': lead.room_type_preference,
    'meal_plan': lead.meal_plan,
}

# We want to simulate the exact call made when "хочется всем вместе" was sent by the guest
# Let's get the conversation history *before* the cutoff message
conversation_history = [
    {"role": "user", "content": "Здравствуйте"},
    {"role": "user", "content": "Хотим спросить по поводу вашего отля"},
    {"role": "assistant", "content": "Здравствуйте! 🌊\nВы обратились в отель Nomad Camp на южного берегу Иссык-Куля.\nС радостью подскажу по размещению. Подскажите, пожалуйста:\n📅 На какие даты вы планируете отдых?\n👥 Сколько человек будет?"},
    {"role": "user", "content": "на 2 июня, 5 человек"},
    {"role": "assistant", "content": "Прекрасно! На 2 июня для пятерых гостей мы можем предложить несколько вариантов размещения:\n\nВариант 1: Три номера категории \"Стандарт\"\n*   Два двухместных номера и один одноместный.\n*   Стоимость без питания: 15 700 сомов за ночь.\n*   Номера будут расположены рядом, если это возможно.\n\nВариант 2: Три номера категории \"Комфорт\"\n*   Два двухместных номера и один одноместный.\n*   Стоимость без питания: 26 500 сомов за ночь.\n*   Номера будут расположены рядом, если это возможно.\n\nКакой вариант вам больше подходит? 😊"}
]

# Let's call the API with different max_tokens
for test_tokens in [100, 300, 1000, 2000]:
    print(f"\n================ TESTING max_tokens={test_tokens} ================")
    # Patch get_config to return test_tokens
    class MockConfig:
        temperature = 0.4
        max_tokens = test_tokens
        
    from apps.flows.models import AIModelConfig
    orig_get_config = AIModelConfig.get_config
    AIModelConfig.get_config = lambda *args, **kwargs: MockConfig()
    
    # We will temporarily intercept the completion create call to inspect finish_reason
    orig_create = ai_service.client.chat.completions.create
    def intercept_create(*args, **kwargs):
        res = orig_create(*args, **kwargs)
        choice = res.choices[0]
        print(f"DEBUG: finish_reason={choice.finish_reason}, length={len(choice.message.content or '')}")
        print(f"DEBUG: content={repr(choice.message.content)}")
        return res
        
    ai_service.client.chat.completions.create = intercept_create
    
    try:
        response = ai_service.generate_response(
            lead=lead,
            message="только эти варианты есть?\n\nнам хочется всем вместе",
            lead_data=lead_data,
            conversation_history=conversation_history
        )
        print("RESULT RESPONSE:", repr(response))
    except Exception as e:
        print("ERROR:", e)
        
    # Restore
    ai_service.client.chat.completions.create = orig_create
    AIModelConfig.get_config = orig_get_config
