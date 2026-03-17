from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import requests
import base64
import mimetypes
import os
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# ดึง API Keys จากไฟล์ .env (รองรับหลายคีย์สำรอง)
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2")
]
# กรองเฉพาะคีย์ที่มีการใส่ค่าจริง (ข้าม placeholder ภาษาไทย)
API_KEYS = [k.strip() for k in API_KEYS if k and not any(p in k for p in ["ใส่_คีย์", "ใส่_API", "YOUR_API"])]

# --- กำหนดค่า AI ให้คงที่และแม่นยำ (Deterministic Settings) ---
AI_CONFIG = {
    "temperature": 0.0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

def call_gemini_api(prompt, is_vision=False, image_data=None):
    """ฟังก์ชันกลางสำหรับเรียก Gemini API พร้อมระบบสลับคีย์และรุ่นโมเดลอัตโนมัติ (Double Fallback)"""
    last_error = "No API Keys configured"
    
    # รายชื่อรุ่นโมเดลที่จะพยายามเรียก (เรียงจากใหม่ไปเก่า)
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest"
    ]
    
    for key in API_KEYS:
        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                
                # Vision supports varies, some models might not support it, but we try anyway
                if is_vision:
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {"inline_data": image_data}
                            ]
                        }],
                        "generationConfig": AI_CONFIG
                    }
                else:
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": AI_CONFIG
                    }
                
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                res_json = response.json()
                
                if response.status_code == 200:
                    if 'candidates' in res_json:
                        return res_json['candidates'][0]['content']['parts'][0]['text']
                    else:
                        last_error = f"API Response Error ({model_name}): {json.dumps(res_json)}"
                        continue # ลองรุ่นอื่นต่อ
                elif response.status_code in [429, 403, 400, 404]:
                    last_error = f"Key/Model Error ({model_name} - {response.status_code}): {res_json.get('error', {}).get('message', 'Unknown error')}"
                    continue # ลองรุ่นอื่นต่อ หรือ Key อื่น
                else:
                    last_error = f"HTTP {response.status_code} ({model_name}): {response.text}"
                    continue
            except Exception as e:
                last_error = f"Exception ({model_name}): {str(e)}"
                continue
            
    return {"error": last_error}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    user_text = request.form.get('text_input')
    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    # ปรังปรุง Prompt ให้รองรับระดับภาษาไทย (Registers)
    prompt_text = f"""
    คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese)
    ข้อความที่ต้องการให้แปล: "{user_text}"
    
    ภารกิจ:
    - หากคุณได้รับภาษาไทย: แปลเป็นภาษาญี่ปุ่น 3 ระดับ (Casual, Polite, Business) พร้อมกำกับ [Romaji]
    - หากคุณได้รับภาษาญี่ปุ่น: แปลเป็นภาษาไทย 2 ระดับ
        1. **สุภาพ/ทางการ**: ใช้ในบริบททำงานหรือส่งข้อความหาหัวหน้า (ใช้ครับ/ค่ะ, ภาษาสุภาพ)
        2. **ทั่วไป/เป็นกันเอง**: ใช้คุยกับเพื่อนหรือคนสนิท
    
    ตอบกลับเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
    {{
        "casual": "คำแปลระดับเป็นกันเอง",
        "polite": "คำแปลระดับสุภาพ",
        "business": "คำแปลระดับทางการ/ธุรกิจ"
    }}
    ตัวอย่าง (TH->JP): "polite": "おはようございます [Ohayou Gozaimasu]"
    ตัวอย่าง (JP->TH): "polite": "สวัสดีครับ"
    """
    
    result = call_gemini_api(prompt_text)
    
    if isinstance(result, dict) and "error" in result:
        status_code = 429 if "429" in str(result.get("error")) else 500
        return jsonify(result), status_code
        
    try:
        clean_json = result.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(clean_json))
    except Exception as e:
        return jsonify({"error": f"JSON Parse Error: {str(e)}", "ai_response": result}), 500

@app.route('/generate_doc', methods=['POST'])
def generate_doc():
    try:
        # Handle both JSON and Form data (for file uploads)
        if request.is_json:
            data = request.json
        else:
            data = request.form
            
        doc_type = data.get('type', 'email')
        recipient = data.get('recipient', 'ลูกค้า/หัวหน้า')
        date_val = data.get('date', '')
        topic = data.get('topic', '')
        
        if not topic:
             return jsonify({"error": "กรุณาระบุหัวข้อหรือข้อมูลดิบสำหรับร่างเอกสารครับ"})

        # Check for optional file attachment for reference
        reference_text = ""
        if 'document' in request.files:
            ref_file = request.files['document']
            if ref_file.filename != '':
                if ref_file.filename.endswith(('.txt', '.md')):
                    reference_text = ref_file.read().decode('utf-8')
                elif ref_file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Optional: Add image OCR here if needed later
                    pass

        # Handle structured JSON from dynamic fields
        context_str = ""
        try:
            topic_obj = json.loads(topic)
            for key, val in topic_obj.items():
                context_str += f"{val}\n"
        except:
            context_str = topic

        if reference_text:
            context_str += f"\nข้อมูลอ้างอิงจากเอกสารเดิม: {reference_text}"

        # Build specialized prompt based on industry focus
        prompt_text = f"""
    ในฐานะผู้เชี่ยวชาญด้านงานเอกสารในโรงงานไม้ที่ญี่ปุ่น
    จงเขียนเอกสาร/อีเมลภาษาญี่ปุ่น โดยใช้ข้อมูลดังนี้:
    
    วันที่: {date_val}
    ประเภท: {doc_type} (หากเป็น leave_request ให้เขียนใบลาหรือแจ้งลาอย่างเป็นทางการ)
    ผู้รับ: {recipient}
    เนื้อหาหลัก: 
    {context_str}
    
    รายละเอียด:
    1. ใช้ภาษาญี่ปุ่นระดับที่เหมาะสมกับผู้รับ (Keigo หากเป็นหัวหน้าหรือลูกค้า)
    2. ระบุวันที่ {date_val} ลงในส่วนหัวหรือส่วนที่เกี่ยวข้องของเอกสารให้ถูกต้องตามธรรมเนียมญี่ปุ่น (ห้ามข้ามเรื่องวันที่)
    3. หากเป็นใบลา (Leave Request) ให้ใช้แพทเทิร์นการลาที่สุภาพและดูเป็นมืออาชีพที่สุด
    4. ใช้ศัพท์เทคนิคงานไม้ (Timber Industry) หากมีการกล่าวถึงงาน
    5. จัดรูปแบบให้เหมือนเอกสารจริง (มีคำขึ้นต้น, เนื้อหา, คำลงท้าย)
    6. หากเป็นรายงานประจำสัปดาห์ (Weekly Report) ให้จัดรูปแบบเป็นหัวข้อ (Bullet points)
    7. หากมีข้อมูลอ้างอิงจากเอกสารเดิม ให้รักษาความหมายเดิมแต่ปรับภาษาให้เป็นมืออาชีพขึ้น
        
    ตอบกลับมาเฉพาะ "เนื้อหาเอกสารภาษาญี่ปุ่น" เท่านั้น (ไม่ต้องมีคำนำหรือคำส่งท้าย)
    """
        
        result = call_gemini_api(prompt_text)
        if isinstance(result, dict) and "error" in result:
            status_code = 429 if "429" in str(result.get("error")) else 500
            return jsonify(result), status_code
            
        return jsonify({"result": result.strip()})

    except Exception as e:
        return jsonify({"error": f"Internal Error: {str(e)}"}), 500

@app.route('/search_glossary', methods=['POST'])
def search_glossary():
    try:
        data = request.json
        term = data.get('term', '')

        if not term:
             return jsonify({"error": "กรุณาระบุคำศัพท์"})

        # ปรับจูน Prompt ให้รองรับมุมมองเจ้าของภาษา (Mother-Tongue Perspective)
        ui_lang = data.get('ui_lang', 'th')
        target_explain = "ภาษาไทย" if ui_lang == "th" else "ภาษาญี่ปุ่น"

        prompt_text = f"""
        คุณคือพจนานุกรมอัจฉริยะ (Thai ↔ Japanese) ที่เชี่ยวชาญด้านอุตสาหกรรมไม้ (Timber Industry)
        และมีความเข้าใจลึกซึ้งในมุมมองของผู้ใช้งาน (User-Centric Perspective)
        
        ข้อมูลผู้ใช้งาน:
        - คำค้นหา (Search Term): "{term}"
        - ภาษาเมนูที่ผู้ใช้ใช้ (UI Language): {ui_lang}
        - ภาษาที่ต้องใช้ในการอธิบาย (Definition Language): {target_explain}
        
        กฎการทำงาน (Rules):
        1. **การวิเคราะห์ภาษา**: ตรวจสอบว่า "{term}" คือภาษาอะไร
        2. **คำแปลเป้าหมาย (term_target)**: ต้องเป็นคำแปลที่มีความหมายเดียวกับ "{term}" ใน "อีกภาษาหนึ่ง" เสมอ
        3. **การอธิบาย (definition)**: ต้องอธิบายความหมายเป็น "{target_explain}" เท่านั้น (เพื่อความเข้าใจลึกซึ้งของผู้ใช้งาน)
        4. **คำศัพท์เทคนิค**: หากเป็นคำย่อหรือคำเทคนิคไม้ (เช่น Mat_Width, KAK, BZI) ให้ขยายความหมายตามมาตรฐานโรงเลื่อย/โรงงานไม้
        
        ตอบกลับเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {{
            "term_main": "คำค้นหาต้นฉบับ",
            "term_target": "คำแปลในอีกภาษา (หากค้นด้วยไทย->แปลญี่ปุ่น, หากค้นด้วยญี่ปุ่น->แปลไทย)",
            "reading": "คำอ่าน (Romaji/Furigana) หากคำนั้นมีภาษาญี่ปุ่นเกี่ยวข้อง",
            "definition": "คำอธิบายความหมายโดยละเอียด (เป็น{target_explain})",
            "example_jp": "ตัวอย่างประโยคญี่ปุ่นที่เกี่ยวข้อง",
            "example_th": "ตัวอย่างประโยคไทยที่แปลจากประโยคญี่ปุ่นข้างต้น"
        }}
        """

        result = call_gemini_api(prompt_text)
        
        if isinstance(result, dict) and "error" in result:
            status_code = 429 if "429" in str(result.get("error")) else 500
            return jsonify(result), status_code

        clean_json = result.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(clean_json))

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/analyze_politeness', methods=['POST'])
def analyze_politeness():
    try:
        data = request.json
        text = data.get('text', '')
        recipient = data.get('recipient', 'ทั่วไป')

        if not text:
             return jsonify({"error": "กรุณาระบุข้อความ"})

        prompt_text = f"""
        คุณคือผู้เชี่ยวชาญด้านภาษาญี่ปุ่นและระดับความสุภาพ (Keigo) อ้างอิงมาตรฐาน Bunkacho
        จงวิเคราะห์ประโยคนี้: "{text}"
        สำหรับผู้รับสารที่เป็น: "{recipient}"
        
        ตอบกลับมาเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {{
            "original_text": "{text}",
            "analysis": "วิเคราะห์ข้อผิดพลาดหรือจุดที่ควรปรับปรุง",
            "suggestion": "ประโยคที่แนะนำให้ใช้ (ภาษาญี่ปุ่น)",
            "explanation": "คำอธิบายไวยากรณ์และความสุภาพ"
        }}
        """

        result = call_gemini_api(prompt_text)
        
        if isinstance(result, dict) and "error" in result:
            status_code = 429 if "429" in str(result.get("error")) else 500
            return jsonify(result), status_code

        clean_json = result.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(clean_json))

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/vision_ocr', methods=['POST'])
def vision_ocr():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "ไม่พบไฟล์รูปภาพ"})
        
        image_file = request.files['image']
        image_data = image_file.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')
        mime_type = image_file.mimetype 

        if mime_type == 'application/octet-stream':
            guessed_type, _ = mimetypes.guess_type(image_file.filename)
            if guessed_type:
                mime_type = guessed_type

        image_part = {
            "mime_type": mime_type,
            "data": base64_image
        }

        prompt_text = """
        ดูรูปภาพนี้แล้ว:
        1. ถอดข้อความภาษาญี่ปุ่นที่อยู่ในภาพออกมา (OCR) - เน้นฉลากสินค้าหรือเอกสารหน้างาน
        2. แปลข้อความเป็นภาษาไทย
        3. สรุปใจความสำคัญสั้นๆ
        
        ตอบกลับมาเป็น JSON ดังนี้ (ไม่ต้องมี markdown):
        {
            "original_text": "ข้อความภาษาญี่ปุ่นที่ถอดได้",
            "translated_text": "คำแปลภาษาไทย",
            "summary": "สรุปสั้นๆ สำหรับคนทำงาน"
        }
        """

        result = call_gemini_api(prompt_text, is_vision=True, image_data=image_part)
        
        if isinstance(result, dict) and "error" in result:
            status_code = 429 if "429" in str(result.get("error")) else 500
            return jsonify(result), status_code

        clean_json = result.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(clean_json))

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)