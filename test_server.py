import requests
import json

url = "http://127.0.0.1:5000/generate_doc"
payload = {
    "topic": "Testing",
    "type": "email",
    "tone": "business",
    "recipient": "Boss"
}
headers = {'Content-Type': 'application/json'}

try:
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print("-" * 20)
    
    # Test Politeness Analysis
    url_politeness = "http://127.0.0.1:5000/analyze_politeness"
    payload_politeness = {
        "text": "Mizu kudasai",
        "recipient": "Client"
    }
    print(f"Testing {url_politeness}...")
    response = requests.post(url_politeness, headers=headers, data=json.dumps(payload_politeness))
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(response.text)

except Exception as e:
    print(f"Connection Error: {e}")
