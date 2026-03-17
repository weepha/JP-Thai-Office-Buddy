import requests

url = "http://127.0.0.1:5000/translate"
data = {"text_input": "สวัสดี"}
response = requests.post(url, data=data)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
