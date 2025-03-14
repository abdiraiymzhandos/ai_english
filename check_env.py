import os
from dotenv import load_dotenv
from openai import OpenAI

# .env жүктеу
load_dotenv()

# API кілтті алу
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ OPENAI_API_KEY табылмады! .env файлын тексеріңіз.")
    exit()

print(f"✅ OPENAI_API_KEY жүктелді: {api_key[:5]}...")

# OpenAI клиентін API кілтімен тікелей инициализациялау
client = OpenAI(api_key=api_key)

# Модельдер тізімін алу
print(client.models.list())
