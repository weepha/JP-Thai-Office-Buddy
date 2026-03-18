from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import requests
from pypdf import PdfReader
import base64
import mimetypes
import os
import time
from dotenv import load_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# ดึง API Keys จากไฟล์ .env (รองรับ GEMINI_API_KEY และ GEMINI_API_KEY_1-5)
API_KEYS = [os.getenv("GEMINI_API_KEY")] + [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]
# กรองเฉพาะคีย์ที่มีการใส่ค่าจริง (ข้าม placeholder ภาษาไทย)
API_KEYS = [k.strip() for k in API_KEYS if k and not any(p in k for p in ["ใส่_คีย์", "ใส่_API", "YOUR_API"])]

# --- กำหนดค่า AI ให้คงที่และแม่นยำ (Deterministic Settings) ---
AI_CONFIG = {
    "temperature": 0.0,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

def try_extract_json(text):
    """ฟังก์ชันช่วยสกัด JSON ออกจากข้อความของ AI ที่อาจมีส่วนเกิน"""
    try:
        # พยายามหากลุ่มข้อความที่อยู่ใน { ... }
        import re
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        
        # ล้าง markdown และช่องว่าง
        clean_json = text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"JSON Parse Error: {e} | Original text: {text}")
        return None

def call_gemini_api(prompt, is_vision=False, image_data=None):
    """ฟังก์ชันกลางสำหรับเรียก Gemini API พร้อมระบบสลับคีย์และรุ่นโมเดลอัตโนมัติ (Double Fallback)"""
    last_error = "No API Keys configured"
    
    # รายชื่อรุ่นโมเดลที่จะพยายามเรียก (Fallback List - จัดลำดับตามความน่าเชื่อถือและที่มีใช้งานจริง)
    models_to_try = [
        "gemini-flash-latest",     # เสถียรที่สุดในเวอร์ชันปัจจุบัน
        "gemini-2.0-flash",        # รวดเร็วและมีความฉลาดสูง
        "gemini-1.5-flash",        # สำหรับบาง API Key ที่อาจระบุรุ่นตายตัว
        "gemini-pro-latest",
        "gemini-1.5-pro",
        "gemini-1.5-flash-8b"
    ]
    
    last_error_data = {"error": "ไม่สามารถติดต่อ AI ได้ในขณะนี้ (ตรวจสอบ API Key หรืออินเทอร์เน็ตครับ)"}

    for model_name in models_to_try:
        for key_index, key in enumerate(API_KEYS):
            try:
                # Log the start of the attempt
                current_try = f"Attempt: [Model: {model_name}] [Key: {key_index+1}/{len(API_KEYS)}]"
                print(f"DEBUG: {current_try} - Sending request...")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                
                payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": AI_CONFIG}
                if is_vision:
                    payload["contents"][0]["parts"].append({"inline_data": image_data})
                
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                res_json = response.json()
                
                if response.status_code == 200:
                    cand = res_json.get('candidates', [{}])[0]
                    if 'content' in cand:
                        print(f"DEBUG: Success with {model_name}")
                        return cand['content']['parts'][0]['text']
                    else:
                        finish_reason = cand.get('finishReason', 'Unknown')
                        last_error = f"AI Blocked (Reason: {finish_reason})"
                        print(f"DEBUG: {model_name} blocked response. Reason: {finish_reason}")
                        continue
                
                else:
                    msg = res_json.get('error', {}).get('message', 'Unknown API Error')
                    status_code = response.status_code
                    last_error_data = {"error": f"API Error ({model_name} - {status_code}): {msg}"}
                    print(f"DEBUG: {model_name} failed with {status_code}: {msg}")
                    
                    if status_code == 429:
                        # If we hit 429 on one model, the key likely has exhausted its RPM or RPD.
                        if len(API_KEYS) == 1:
                            print(f"DEBUG: Only one key available and it's rate-limited.")
                            import re
                            retry_match = re.search(r'retry in ([\d\.]+)s', msg)
                            wait_msg = f" (กรุณารอประมาณ {retry_match.group(1)} วินาที)" if retry_match else ""
                            return {"error": f"⚠️ โควต้าฟรีของคุณเต็มชั่วคราวครับ{wait_msg}\n\nคำแนะนำ: เพิ่ม API Key ชุดที่ 2 ในไฟล์ .env เพื่อให้ใช้งานได้ต่อเนื่องครับ"}
                        else:
                            print(f"DEBUG: Rate limited. Moving to next key...")
                            time.sleep(1) # Wait a bit
                        continue
                    
                    continue
                    
            except Exception as e:
                last_error_data = {"error": f"Crashed on {model_name}: {str(e)}"}
                print(f"DEBUG: Unexpected error on {model_name}: {str(e)}")
                continue
            
    return last_error_data

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    user_text = request.form.get('text_input')
    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    # ปรับปรุง Prompt ให้รองรับระดับภาษาไทย (Registers) และบังคับการหนีสัญลักษณ์ (Escaping)
    user_text_escaped = user_text.replace('"', '\\"')
    prompt_text = f"""
    คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese)
    ข้อความที่ต้องการให้แปล: "{user_text_escaped}"
    
    ภารกิจ:
    - หากคุณได้รับภาษาไทย: แปลเป็นภาษาญี่ปุ่น 3 ระดับ (Casual, Polite, Business) พร้อมกำกับ [Romaji]
    - หากคุณได้รับภาษาญี่ปุ่น: แปลเป็นภาษาไทย 2 ระดับ
        1. **สุภาพ/ทางการ**: ใช้ในบริบททำงานหรือส่งข้อความหาหัวหน้า (ใช้ครับ/ค่ะ, ภาษาสุภาพ)
        2. **ทั่วไป/เป็นกันเอง**: ใช้คุยกับเพื่อนหรือคนสนิท
    
    ข้อกำหนดด้านรูปแบบ (Format Requirement):
    - ตอบกลับเป็น JSON เท่านั้น
    - **สำคัญมาก**: หากในคำแปลมีเครื่องหมายอัญประกาศ (") ให้ใช้การหนีสัญลักษณ์ (Escape) เป็น \\" เสมอ
    - **สำคัญมาก**: หากมีการขึ้นบรรทัดใหม่ในเนื้อหา ให้ใช้ \\n แทนการขึ้นบรรทัดจริงใน JSON
    
    JSON Structure:
    {{
        "casual": "คำแปลระดับเป็นกันเอง",
        "polite": "คำแปลระดับสุภาพ",
        "business": "คำแปลระดับทางการ/ธุรกิจ"
    }}
    """
    
    result = call_gemini_api(prompt_text)
    
    if isinstance(result, dict) and "error" in result:
        status_code = 429 if "429" in str(result.get("error")) else 500
        # ปรับข้อความ Error ให้เป็นมิตรขึ้นถ้าเป็น 429
        if status_code == 429:
            result["error"] = "⚠️ Gemini Quota Exceeded: โควต้าฟรีเต็มชั่วคราวครับ\n\nวิธีแก้:\n1. รอประมาณ 1-2 นาทีแล้วลองใหม่\n2. เพิ่ม API Key สำรองในไฟล์ .env (GEMINI_API_KEY_2, _3, ...) เพื่อให้ระบบสลับคีย์อัตโนมัติ"
        return jsonify(result), status_code
        
    parsed_data = try_extract_json(result)
    if parsed_data:
        return jsonify(parsed_data)
    else:
        return jsonify({"error": "AI ตอบกลับในรูปแบบที่ประมวลผลไม่ได้ครับ", "ai_response": result}), 500

@app.route('/verify_content', methods=['POST'])
def verify_content():
    """เอนพอยต์เฉพาะสำหรับการตรวจสอบเนื้อหาภาษาญี่ปุ่น (แปลกลับเป็นไทยอย่างละเอียดเพียงระดับเดียว)"""
    jp_text = request.form.get('text_input')
    if not jp_text:
        return jsonify({"error": "No text provided"}), 400

    prompt_text = f"""
    คุณคือผู้เชี่ยวชาญการตรวจเอกสาร (Japanese -> Thai)
    ภารกิจ: แปลข้อความภาษาญี่ปุ่นนี้กลับเป็นภาษาไทยอย่างละเอียดที่สุด เพื่อให้ผู้ใช้ตรวจสอบความถูกต้องของเนื้อหา
    
    ข้อความภาษาญี่ปุ่น: 
    "{jp_text.replace('"', '\\"')}"
    
    ข้อกำหนด:
    1. แปลให้ครบถ้วนทุกประเด็น ห้ามย่อความ
    2. ใช้ระดับภาษาที่สุภาพและเป็นทางการ (Polite/Business)
    3. หากมีการใช้คำศัพท์เฉพาะทางอุตสาหกรรมไม้ ให้ระบุคำแปลที่ถูกต้อง
    4. **สำคัญ: ให้ตอบกลับเฉพาะคำแปลภาษาไทยเท่านั้น ไม่ต้องใช้ JSON ไม่ต้องมีหัวข้อ หรือคำนำใดๆ**
    """
    
    result = call_gemini_api(prompt_text)
    
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
        
    # คืนค่าเป็นข้อความดิบ (Plain Text) เพื่อความเสถียรสูงสุด
    return result.strip() if result else "ไม่สามารถประมวลผลได้"

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
        
        # Check for optional file attachment for reference
        reference_text = ""
        is_file_attached = False
        if 'document' in request.files:
            ref_file = request.files['document']
            if ref_file.filename != '':
                is_file_attached = True
                if ref_file.filename.endswith(('.txt', '.md')):
                    reference_text = ref_file.read().decode('utf-8')
                elif ref_file.filename.lower().endswith('.pdf'):
                    try:
                        reader = PdfReader(ref_file)
                        for page in reader.pages:
                            reference_text += page.extract_text() + "\n"
                        
                        if not reference_text.strip():
                            return jsonify({"error": "ไม่พบข้อความในไฟล์ PDF นี้ครับ (อาจเป็นไฟล์ที่สแกนมาเป็นรูปภาพ) กรุณาลองใช้การสแกนรูปภาพ (OCR) แทนครับ"})
                    except Exception as e:
                        print(f"PDF Error: {e}")
                        return jsonify({"error": "ไม่สามารถอ่านไฟล์ PDF นี้ได้ครับ ไฟล์อาจถูกล็อกหรือเสียหาย"})
                elif ref_file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Optional: Add image OCR here if needed later
                    pass
        
        if not topic and not reference_text:
             return jsonify({"error": "กรุณาระบุหัวข้อหรือแนบไฟล์เอกสารที่ต้องการให้ปรับปรุงครับ"})

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
    คุณคือผู้เชี่ยวชาญด้านงานเอกสารและการใช้ภาษาญี่ปุ่นในโรงงานไม้ (Timber Industry)
    ภารกิจของคุณคือ: เขียนหรือปรับปรุงเอกสารภาษาญี่ปุ่นตามข้อมูลที่ได้รับ
    
    วันที่: {date_val}
    ประเภทเอกสารที่ต้องการ: {doc_type}
    ผู้รับสาร: {recipient}
    
    ข้อมูลหลักจากผู้ใช้:
    {context_str}
    
    {"[โหมดปรับปรุงเอกสารเดิม]" if not topic and reference_text else ""}
    
    {f"[สำคัญ: มีไฟล์แนบขื่อ {ref_file.filename}] ให้เพิ่มประโยคภาษาญี่ปุ่นแจ้งผู้รับว่ามีไฟล์แนบมาด้วย (เช่น 「詳細は添付ファイルをご参照ください」)" if is_file_attached and doc_type == "email" else ""}
    
    รายละเอียดและข้อกำหนด:
    1. ใช้ภาษาญี่ปุ่นระดับที่เหมาะสม (Keigo หากส่งหาหัวหน้า/ลูกค้า) 
    2. ระบุวันที่ {date_val} ลงในเอกสารให้ถูกต้องตามธรรมเนียมญี่ปุ่น (ห้ามข้าม)
    3. หากเป็นโหมดปรับปรุงเอกสารเดิม: ให้เน้นการแก้ไวยากรณ์ การเลือกใช้คำที่สุภาพขึ้น และการจัด Format ให้เป็นระเบียบตามประเภทเอกสารที่เลือก **โดยห้ามตัดทอนข้อมูล (Do NOT summarize) และต้องรักษาเนื้อหาเดิมเอาไว้ให้ครบถ้วนที่สุดทุกประเด็น**
    4. หากเป็นใบลา (Leave Request): ใช้แพทเทิร์นที่เป็นมาตรฐานและสุภาพที่สุด
    5. ใช้คำศัพท์เฉพาะพนักงานโรงงานไม้ (เช่น プレカット, 木材, 寸法) หากเนื้อหามีการกล่าวถึง
    6. จัดรูปแบบเอกสารให้สมบูรณ์ (คำขึ้นต้น, เนื้อหา, คำลงท้าย)
    7. หากเป็นรายงานรายสัปดาห์ (Weekly Report): จัดเป็นหัวข้อที่อ่านง่าย (Key progress, Next steps) **แต่ต้องนำข้อมูลจากต้นฉบับมาใส่ให้ครบ ห้ามย่อเป็นสรุปสั้นๆ**
    8. **หากมีข้อมูลอ้างอิงจากไฟล์ และเป็นประเภทอีเมล: ให้เขียนระบุในเนื้อหาว่ามีไฟล์แนบมาด้วยให้ชัดเจน**
    9. **ข้อสำคัญ: ห้ามใช้สัญลักษณ์ Markdown เช่น **หนา**, ### หัวข้อ หรือ --- เส้นคั่น ให้ใช้การเว้นวรรคและขึ้นบรรทัดใหม่ในการแบ่งหัวข้อแทน เพื่อให้ผู้ใช้นำไปวางใน Word ได้ทันทีโดยไม่ต้องลบจุดเหล่านี้**
    
    ตอบกลับเฉพาะ "เนื้อหาเอกสารภาษาญี่ปุ่น" เท่านั้น (ไม่ต้องมีคำนำ/สรุปภาษาไทย)
    """
        
        result = call_gemini_api(prompt_text)
        
        if isinstance(result, dict) and "error" in result:
            status_code = 429 if "429" in str(result.get("error")) else 500
            return jsonify(result), status_code
            
        return jsonify({"result": result.strip() if result else ""})

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
        - คำค้นหา (Search Term): "{term.replace('"', '\\"')}"
        - ภาษาเมนูที่ผู้ใช้ใช้ (UI Language): {ui_lang}
        - ภาษาที่ต้องใช้ในการอธิบาย (Definition Language): {target_explain}
        
        กฎการทำงาน (Rules):
        1. **การวิเคราะห์ภาษา**: ตรวจสอบว่า "{term}" คือภาษาอะไร
        2. **คำแปลเป้าหมาย (term_target)**: ต้องเป็นคำแปลที่มีความหมายเดียวกับ "{term}" ใน "อีกภาษาหนึ่ง" เสมอ
        3. **การอธิบาย (definition)**: ต้องอธิบายความหมายเป็น "{target_explain}" เท่านั้น (เพื่อความเข้าใจลึกซึ้งของผู้ใช้งาน)
        4. **คำศัพท์เทคนิค**: หากเป็นคำย่อหรือคำเทคนิคไม้ (เช่น Mat_Width, KAK, BZI) ให้ขยายความหมายตามมาตรฐานโรงเลื่อย/โรงงานไม้
        5. **สำคัญมาก**: ใช้ JSON Format และต้องหนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \\" และใช้ \\n สำหรับการขึ้นบรรทัดใหม่
        
        ตอบกลับเป็น JSON ดังนี้:
        {{
            "term_main": "คำค้นหาต้นฉบับ",
            "term_target": "คำแปลในอีกภาษา",
            "reading": "คำอ่าน (Romaji/Furigana)",
            "definition": "คำอธิบายความหมายโดยละเอียด",
            "example_jp": "ตัวอย่างประโยคญี่ปุ่น",
            "example_th": "ตัวอย่างประโยคไทย"
        }}
        """

        result = call_gemini_api(prompt_text)
        
        if isinstance(result, dict) and "error" in result:
            status_code = 429 if "429" in str(result.get("error")) else 500
            return jsonify(result), status_code

        parsed_data = try_extract_json(result)
        if parsed_data:
            return jsonify(parsed_data)
        else:
            return jsonify({"error": "ไม่สามารถประมวลผลคำศัพท์ได้ครับ", "ai_response": result}), 500

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
        จงวิเคราะห์ประโยคนี้: "{text.replace('"', '\\"')}"
        สำหรับผู้รับสารที่เป็น: "{recipient}"
        
        ตอบกลับมาเป็น JSON (หนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \\" และใช้ \\n สำหรับขึ้นบรรทัดใหม่):
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
            
        parsed_data = try_extract_json(result)
        if parsed_data:
            return jsonify(parsed_data)
        else:
            return jsonify({"error": "ไม่สามารถวิเคราะห์ความสุภาพได้ครับ", "ai_response": str(result)}), 500

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
        
        ตอบกลับมาเป็น JSON เท่านั้น (หนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \\" และใช้ \\n สำหรับขึ้นบรรทัดใหม่):
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

        parsed_data = try_extract_json(result)
        if parsed_data:
            return jsonify(parsed_data)
        else:
            return jsonify({"error": "ไม่สามารถอ่านรูปภาพได้ครับ", "ai_response": result}), 500

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)