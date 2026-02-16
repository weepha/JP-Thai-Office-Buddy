import google.generativeai as genai

# --- ใส่ API Key ของคุณตรงนี้ ---
my_api_key = "AIzaSyCZS5RI77o86YsdvmoX_mm835hfSlz2PCc" 
genai.configure(api_key=my_api_key)

print("--- กำลังทดสอบหาชื่อโมเดลที่ใช้ได้... ---")

# รายชื่อโมเดลทั้งหมดที่เราจะลองสุ่มดู
candidate_models = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-001",
    "gemini-1.0-pro",
    "gemini-pro"
]

found = False

for model_name in candidate_models:
    try:
        print(f"กำลังลอง: {model_name} ...", end=" ")
        model = genai.GenerativeModel(model_name)
        # ลองส่งข้อความสั้นๆ ไปเทส
        response = model.generate_content("Hello")
        
        print("✅ สำเร็จ! (ใช้ชื่อนี้ได้เลย)")
        print(f"\n>>> สรุป: ให้คุณกลับไปแก้ในไฟล์ app.py เป็น:")
        print(f"model = genai.GenerativeModel('{model_name}')")
        found = True
        break # เจอแล้วหยุดเลย
    except Exception as e:
        print(f"❌ ไม่ได้ (Error: {e})")

if not found:
    print("\n⚠️ ยังหาไม่เจอเลย: ลองเช็ค API Key อีกที หรือลอง list_models() ดู")