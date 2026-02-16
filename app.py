from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import requests 

app = Flask(__name__)
CORS(app)

# --- ใส่ API Key ของคุณตรงนี้ ---
API_KEY = "AIzaSyCZS5RI77o86YsdvmoX_mm835hfSlz2PCc"

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
        คุณคือพจนานุกรมศัพท์ธุรกิจญี่ปุ่น-ไทย
        จงอธิบายคำศัพท์: "{term}"
        
        ตอบกลับมาเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {{
            "term_jp": "คำศัพท์ภาษาญี่ปุ่น (Kanji/Kana)",
            "definition": "ความหมายและการใช้งานในบริบททำงาน",
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

if __name__ == '__main__':
    app.run(debug=True)