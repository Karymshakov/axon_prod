import os
from openai import OpenAI
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv(dotenv_path="backend/.env")
# Fallback load from root .env
load_dotenv()

api_key = os.environ.get('CAYU_GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
base_url = 'https://generativelanguage.googleapis.com/v1beta/openai/'
model = os.environ.get('GEMINI_MODEL') or 'gemini-2.5-flash'

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

system_prompt = (
    "You are a hotel CRM assistant. Given a conversation between a guest and a hotel agent, "
    "write a single factual 10-15 word summary of the current booking inquiry. "
    "Focus on: room type, dates, guest count, meal plan, current conversation stage. "
    "Match the language the guest is using (Russian, Kyrgyz, or English). "
    "Return ONLY the summary — no quotes, no punctuation at the end, no extra text."
)

conversation = """
Гость: Здравствуйте, мы бы хотели забронировать номер на 2 июня для 5 человек.
Агент: Здравствуйте! Будем рады вас разместить. Подскажите, пожалуйста, будут ли с вами дети и какого они возраста?
"""

try:
    for max_tokens in [10, 30, 60, 150, 300, 500]:
        print(f"\n--- Testing max_tokens = {max_tokens} ---")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': conversation},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        choice = response.choices[0]
        content = choice.message.content
        finish_reason = choice.finish_reason
        usage = getattr(response, 'usage', None)
        print(f"Finish Reason: {finish_reason}")
        if usage:
            print(f"Usage: prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}, total_tokens={usage.total_tokens}")
        print(f"Response: {repr(content)}")
except Exception as e:
    print(f"Error occurred: {e}")
