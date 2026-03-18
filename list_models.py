import requests
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY_1")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
response = requests.get(url)
with open("models_list_utf8.txt", "w", encoding="utf-8") as f:
    f.write(f"Status: {response.status_code}\n")
    if response.status_code == 200:
        models = response.json().get('models', [])
        for m in models:
            f.write(f"- {m['name']}\n")
    else:
        f.write(response.text)
print("Done")
