from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import requests 

app = Flask(__name__)
CORS(app)

# --- ใส่ API Key ของคุณตรงนี้ ---
API_KEY = "AIzaSyDJ1y-GvV_Uf2mMQvPuYFOx_h1Un-svGAc"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    try:
        user_text = request.form['text_input']
        
        # --- จุดที่แก้ไข: ใช้รุ่น 'gemini-flash-latest' (ตัวนี้ฟรีและเสถียรสุด) ---
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
        
        prompt_text = f"""
        คุณคือผู้ช่วยแปลภาษาไทยเป็นญี่ปุ่น
        จงแปลประโยคนี้: "{user_text}"
        ให้ออกมาเป็น 3 ระดับความสุภาพ ตอบกลับมาเฉพาะรูปแบบ JSON เท่านั้น (ไม่ต้องมี markdown) ดังนี้:
        {{
            "casual": "...",
            "polite": "...",
            "business": "..."
        }}
        """

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            data = response.json()
            ai_text = data['candidates'][0]['content']['parts'][0]['text']
            clean_json = ai_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_json)
            return jsonify(result)
        else:
            return jsonify({"error": f"Google API Error: {response.text}"})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/generate_doc', methods=['POST'])
def generate_doc():
    try:
        data = request.json
        topic = data.get('topic', '')
        doc_type = data.get('type', 'email') # email, report, etc.
        tone = data.get('tone', 'business') # polite, business, casual
        recipient = data.get('recipient', 'ลูกค้า/หัวหน้า')

        if not topic:
             return jsonify({"error": "กรุณาระบุหัวข้อเอกสาร"})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
        
        prompt_text = f"""
        คุณคือผู้ช่วยเลขานุการมืออาชีพในบริษัทญี่ปุ่น
        จงร่างเอกสารภาษาญี่ปุ่นดังนี้:
        - ประเภท: {doc_type}
        - หัวข้อ/ใจความสำคัญ: "{topic}"
        - ระดับภาษา: {tone}
        - ผู้รับสาร: {recipient}
        
        ข้อแนะนำเพิ่มเติม:
        - หากเป็น 'nippou' (รายงานประจำวัน) ให้ใช้ฟอร์แมตมาตรฐาน Nippou (業務内容, 所感, 明日の予定 ฯลฯ)
        
        ตอบกลับมาเฉพาะเนื้อหาเอกสารภาษาญี่ปุ่นที่สมบูรณ์เท่านั้น (ไม่ต้องมีคำอธิบายเพิ่มเติม)
        """

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            data = response.json()
            ai_text = data['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"result": ai_text.strip()})
        else:
            return jsonify({"error": f"Google API Error: {response.text}"})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/search_glossary', methods=['POST'])
def search_glossary():
    try:
        data = request.json
        term = data.get('term', '')

        if not term:
             return jsonify({"error": "กรุณาระบุคำศัพท์"})

        # Use the same model as others
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
        
        prompt_text = f"""
        คุณคือพจนานุกรมศัพท์ธุรกิจธุรกิจญี่ปุ่น-ไทย
        จงอธิบายคำศัพท์: "{term}"
        
        ตอบกลับมาเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {{
            "term_jp": "คำศัพท์ภาษาญี่ปุ่น (Kanji/Kana)",
            "definition": "ความหมายและการใช้งานในบริบททำงาน",
            "politeness_level": "ระดับความสุภาพ (Normal/Polite/Honorific)",
            "example_jp": "ประโยคตัวอย่างภาษาญี่ปุ่น",
            "example_th": "คำแปลประโยคตัวอย่าง"
        }}
        """

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            data = response.json()
            ai_text = data['candidates'][0]['content']['parts'][0]['text']
            clean_json = ai_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_json)
            return jsonify(result)
        else:
            return jsonify({"error": f"Google API Error: {response.text}"})

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/analyze_politeness', methods=['POST'])
def analyze_politeness():
    try:
        data = request.json
        text = data.get('text', '')
        recipient = data.get('recipient', 'ทั่วไป') # e.g., หัวหน้า, ลูกค้า, เพื่อนร่วมงาน

        if not text:
             return jsonify({"error": "กรุณาระบุข้อความ"})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
        
        prompt_text = f"""
        คุณคือผู้เชี่ยวชาญด้านภาษาญี่ปุ่นและระดับความสุภาพ (Keigo)
        จงวิเคราะห์ประโยคนี้: "{text}"
        สำหรับผู้รับสารที่เป็น: "{recipient}"
        
        ตอบกลับมาเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {{
            "original_text": "{text}",
            "analysis": "วิเคราะห์ข้อผิดพลาดหรือจุดที่ควรปรับปรุง",
            "suggestion": "ประโยคที่แนะนำให้ใช้ (ภาษาญี่ปุ่น)",
            "explanation": "คำอธิบายว่าทำไมถึงแนะนำแบบนี้"
        }}
        """

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            data = response.json()
            ai_text = data['candidates'][0]['content']['parts'][0]['text']
            clean_json = ai_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_json)
            return jsonify(result)
        else:
            return jsonify({"error": f"Google API Error: {response.text}"})

    except Exception as e:
        return jsonify({"error": str(e)})

import base64

@app.route('/vision_ocr', methods=['POST'])
def vision_ocr():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "ไม่พบไฟล์รูปภาพ"})
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({"error": "ไม่ได้เลือกรูปภาพ"})

        # Read and encode image to base64
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        mime_type = image_file.mimetype 

        # Fix for Flutter sending application/octet-stream
        if mime_type == 'application/octet-stream':
            import mimetypes
            guessed_type, _ = mimetypes.guess_type(image_file.filename)
            if guessed_type:
                mime_type = guessed_type

        # Use gemini-flash-latest (supports vision)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"
        
        prompt_text = """
        ดูรูปภาพนี้แล้ว:
        1. ถอดข้อความภาษาญี่ปุ่นที่อยู่ในภาพออกมา (OCR)
        2. แปลข้อความเป็นภาษาไทย
        3. ถ้าเป็นเอกสารธุรกิจ ให้สรุปใจความสำคัญสั้นๆ
        
        ตอบกลับมาเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {
            "original_text": "ข้อความภาษาญี่ปุ่นที่ถอดได้",
            "translated_text": "คำแปลภาษาไทย",
            "summary": "สรุปใจความสำคัญ (ถ้ามี)"
        }
        """

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64_image
                        }
                    }
                ]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            data = response.json()
            ai_text = data['candidates'][0]['content']['parts'][0]['text']
            clean_json = ai_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_json)
            return jsonify(result)
        else:
            return jsonify({"error": f"Google API Error: {response.text}"})

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)