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

print(f"Using API Key: {api_key[:10]}...")
print(f"Model: {model}")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

# We will create a large prompt to check the total tokens behavior
prompt_base = "This is a dummy prompt to consume tokens. " * 300
system_prompt = (
    "You are a helpful assistant. "
    "When asked a question, respond with a very long sentence explaining your answer in detail. "
    f"Here is some background context: {prompt_base}"
)

print(f"System prompt length in characters: {len(system_prompt)}")

try:
    for max_tokens in [1000, 2048, 4096, 8192]:
        print(f"\n--- Testing max_tokens = {max_tokens} ---")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Explain the importance of children's education in detail."}
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        choice = response.choices[0]
        content = choice.message.content
        finish_reason = choice.finish_reason
        usage = getattr(response, 'usage', None)
        print(f"Finish Reason: {finish_reason}")
        if usage:
            print(f"Usage: prompt_tokens={usage.prompt_tokens}, completion_tokens={usage.completion_tokens}, total_tokens={usage.total_tokens}")
        else:
            print("No usage metadata returned.")
        print(f"Response length: {len(content)} characters")
        print(f"Response preview: {content[:100]}...")
except Exception as e:
    print(f"Error occurred: {e}")
