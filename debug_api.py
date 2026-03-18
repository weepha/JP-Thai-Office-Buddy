import os
import json
from app import app, API_KEYS

print(f"Detected API Keys: {len(API_KEYS)}")
for i, k in enumerate(API_KEYS):
    print(f"Key {i+1}: {k[:5]}...{k[-5:]}")

with app.test_client() as client:
    print("\nTesting /translate with 'Hello'...")
    response = client.post('/translate', data={'text_input': 'Hello'})
    print(f"Status: {response.status_code}")
    print(f"Data: {response.get_data(as_text=True)}")

    print("\nTesting /search_glossary with 'wood'...")
    response = client.post('/search_glossary', json={'term': 'wood', 'ui_lang': 'th'})
    print(f"Status: {response.status_code}")
    print(f"Data: {response.get_data(as_text=True)[:200]}...")

    print("\nTesting /generate_doc (Weekly Report)...")
    doc_payload = {
        'type': 'weekly_report',
        'recipient': 'Boss',
        'date': '2026-03-18',
        'topic': json.dumps({'work_done': 'Finished sawmill setup', 'issues': 'None', 'next_week': 'Start production'})
    }
    response = client.post('/generate_doc', data=doc_payload)
    print(f"Status: {response.status_code}")
    print(f"Data: {response.get_data(as_text=True)[:100]}...")

    print("\nTesting /analyze_politeness...")
    polite_payload = {'text': 'Mizu nomitai', 'recipient': 'Manager'}
    response = client.post('/analyze_politeness', json=polite_payload)
    print(f"Status: {response.status_code}")
    print(f"Data: {response.get_data(as_text=True)[:200]}...")
