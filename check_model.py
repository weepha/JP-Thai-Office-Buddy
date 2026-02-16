import google.generativeai as genai

# ใส่ API Key ของคุณตรงนี้
genai.configure(api_key="รหัสของคุณที่ copy มาใส่ตรงนี้")

print("--- กำลังดึงรายชื่อโมเดลที่คุณใช้ได้ ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"เกิดข้อผิดพลาด: {e}")