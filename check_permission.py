import requests
import json

# --- ใส่ API Key ของคุณตรงนี้ ---
API_KEY = "AIzaSyCZS5RI77o86YsdvmoX_mm835hfSlz2PCc"

# ยิงไปถาม Google ว่า "ฉันใช้อะไรได้บ้าง?"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

print("--- กำลังตรวจสอบสิทธิ์ของ API Key ---")
try:
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print("✅ เชื่อมต่อสำเร็จ! รายชื่อโมเดลที่คุณใช้ได้คือ:")
        
        found_any = False
        if 'models' in data:
            for m in data['models']:
                # กรองเฉพาะตัวที่ใช้สร้างข้อความได้
                if 'generateContent' in m.get('supportedGenerationMethods', []):
                    print(f"  - {m['name']}") # เช่น models/gemini-1.5-flash
                    found_any = True
        
        if not found_any:
            print("⚠️ เชื่อมต่อได้ แต่ไม่พบโมเดลที่ใช้งานได้เลย (Account อาจมีปัญหา)")
            
    else:
        print(f"❌ เชื่อมต่อไม่ได้ (Error {response.status_code}):")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")