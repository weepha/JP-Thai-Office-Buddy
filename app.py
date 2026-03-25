from flask import Flask, render_template, request, jsonify

from flask_cors import CORS

import json

import requests

from pypdf import PdfReader

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



def call_gemini_api(prompt, is_vision=False, image_data=None, require_json=False):

    """ฟังก์ชันกลางสำหรับเรียก Gemini API พร้อมระบบสลับคีย์และรุ่นโมเดลอัตโนมัติ (Double Fallback)"""

    last_error = "No API Keys configured"

    

    # Reload dotenv to catch any new keys the user just saved without restarting the server

    load_dotenv(override=True)

    current_keys = [os.getenv("GEMINI_API_KEY")] + [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]

    current_keys = [k.strip() for k in current_keys if k and not any(p in k for p in ["ใส่_คีย์", "ใส่_API", "YOUR_API"])]

    

    if not current_keys:

        return {"error": "ไม่พบ API Key ในระบบครับ กรุณาเปิดไฟล์ .env แล้วใส่ GEMINI_API_KEY ก่อนใช้งานครับ"}

        

    last_error_data = {"error": "ไม่สามารถติดต่อ AI ได้ในขณะนี้ (ตรวจสอบ API Key หรืออินเทอร์เน็ตครับ)"}



    # รายชื่อรุ่นโมเดลที่จะพยายามเรียก (Fallback List - จัดลำดับตามความน่าเชื่อถือและที่มีใช้งานจริง)

    models_to_try = [

        "gemini-2.5-flash",        # รุ่นใหม่ล่าสุด

        "gemini-2.0-flash",        # รวดเร็วและมีความฉลาดสูง

        "gemini-flash-latest",     # รุ่นเสถียรล่าสุดแบบออโต้

    ]

    

    for model_name in models_to_try:

        for key_index, key in enumerate(current_keys):

            try:

                # Log the start of the attempt

                current_try = f"Attempt: [Model: {model_name}] [Key: {key_index+1}/{len(current_keys)}]"

                print(f"DEBUG: {current_try} - Sending request...")

                

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"

                

                gen_config = dict(AI_CONFIG)
                if require_json:
                    gen_config["responseMimeType"] = "application/json"
                payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen_config}

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

                    print(f"DEBUG: {model_name} failed with {status_code}: {msg}")

                    

                    if status_code == 429:

                        # If we hit 429 on one model, the key likely has exhausted its RPM or RPD.

                        import re

                        retry_match = re.search(r'retry in ([\d\.]+)s', msg)

                        wait_msg = f" (กรุณารอประมาณ {retry_match.group(1)} วินาที)" if retry_match else ""

                        error_msg = f"429: ⚠️ โควต้าฟรีของคุณเต็มชั่วคราวครับ{wait_msg}\n\nคำแนะนำ: เพิ่ม API Key สำรองในไฟล์ .env เพื่อให้ใช้งานได้ต่อเนื่องครับ"

                        last_error_data = {"error": error_msg}

                        

                        if len(current_keys) == 1:

                            print(f"DEBUG: Only one key available and it's rate-limited.")

                            return last_error_data

                        else:

                            print(f"DEBUG: Rate limited. Moving to next key...")

                            time.sleep(1) # Wait a bit

                        continue

                    

                    # Prevent overwriting a 429 error with a 404/403 from a fallback model

                    if not ("429" in last_error_data.get("error", "")):

                        last_error_data = {"error": f"API Error ({model_name} - {status_code}): {msg}"}

                    

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

    ui_lang = request.form.get('ui_lang', 'th')

    trans_mode = request.form.get('trans_mode', 'read')

    if not user_text:

        return jsonify({"error": "No text provided"}), 400



    user_text_escaped = user_text.replace('"', '\"')

    

    # User Explicit Intent

    is_draft_mode = (trans_mode == 'draft')

    

    if ui_lang == 'th':
        if not is_draft_mode:
            prompt_text = f'''
            คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese)
            ข้อความที่ต้องการแปล/อธิบายความหมาย: "{user_text_escaped}"
            
            ภารกิจ: เป้าหมายของผู้ใช้คือ "อ่านเพื่อทำความเข้าใจ" ไม่ต้องการข้อมูลยืดเยื้อหรือ 3 ระดับ
            1. วิเคราะห์ว่าข้อความเป็นภาษาอะไร และแปลเป็นอีกภาษาหนึ่ง (มักจะเป็นญี่ปุ่นเป็นไทย)
            2. ให้เลือก "แปลออกมาเป็นคำตอบเดียวที่ดีและเป็นธรรมชาติที่สุด" ลงในช่อง "business" (ห้ามให้หลายตัวเลือก ห้ามทำเป็นลิสต์เด็ดขาด)
               - **ถ้าแปลเป็นภาษาญี่ปุ่น**: ต้องใส่คำอ่าน (Romaji) ไว้ในวงเล็บ [ ] ต่อท้ายเสมอด้วย เช่น 素晴らしい [Subarashii]
               - **ถ้าแปลเป็นภาษาไทย**: ไม่ต้องใส่คำอ่านใดๆ พิมพ์แค่คำแปลเท่านั้น เช่น ดีมาก
            3. ใส่ช่อง "casual" ว่า "โหมดอ่านจับใจความ"
            
            ตอบกลับเป็น JSON เท่านั้น (หนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \" และใช้ \n สำหรับการขึ้นบรรทัดใหม่):
            {{
                "casual": "โหมดอ่านจับใจความ",
                "polite": "-",
                "business": "คำแปลทั้งหมดที่อิงตามบริบทและเป็นทางการ พร้อม [คำอ่าน]"
            }}
            '''
        else:
            prompt_text = f'''
            คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese)
            ข้อความที่ต้องการแปล: "{user_text_escaped}"
            
            ภารกิจ: แปลข้อความนี้ออกเป็น 3 ระดับ (แตกย่อย 3 ระดับ) เพื่อให้คนไทยนำไปแต่งประโยคหรือพิจารณาเลือกใช้
            1. ถ้าข้อความเป็นภาษาไทย: ให้แปลเป็นภาษาญี่ปุ่น 3 ระดับ พร้อมกำกับ [Romaji] เพื่อนำไปพูด
            2. ถ้าข้อความเป็นภาษาญี่ปุ่น: ให้แปลเป็นภาษาไทย 3 ระดับ (เป็นกันเอง, สุภาพ, ทางการ) เพื่ออ่านความหมายและบริบท
            
            ตอบกลับเป็น JSON เท่านั้น (หนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \" และใช้ \n สำหรับการขึ้นบรรทัดใหม่):
            {{
                "casual": "คำแปลระดับเป็นกันเอง",
                "polite": "คำแปลระดับสุภาพ",
                "business": "คำแปลระดับทางการ/ธุรกิจ"
            }}
            '''
    else:  # ui_lang == 'jp'
        if not is_draft_mode:
            prompt_text = f'''
            あなたはプロのビジネス翻訳者です。(Thai ↔ Japanese)
            翻訳/意味を説明したい文章: "{user_text_escaped}"
            
            ミッション: ユーザーの目的は「意味を読んで理解すること」です。（3つのレベルや詳細な説明は不要）
            1. 文章がどの言語かを判断し、もう一方の言語（通常はタイ語 -> 日本語）に翻訳してください。
            2. 最適で最も自然な翻訳を「1つだけ」選んで "business" フィールドに記載してください。（複数の選択肢やリスト形式は絶対に禁止）
               - **「タイ語」に翻訳する場合**: 必ずタイ語の読み方（カタカナ）を括弧 [ ] の中に併記してください。 例: ดีมาก [ディーマーク]
               - **「日本語」に翻訳する場合**: 読み方の併記は不要です。そのまま翻訳だけを記載してください。 例: 素晴らしい
            3. "casual" フィールドには "意訳・全体翻訳モード" と記載してください。
            
            JSON形式のみで返答してください (ダブルクォーテーション (") は \" でエスケープし、改行には \n を使用してください):
            {{
                "casual": "意訳・全体翻訳モード",
                "polite": "-",
                "business": "文脈に沿った正確な翻訳内容全体 [読み方]"
            }}
            '''
        else:
            prompt_text = f'''
            あなたは高度なAI翻訳アシスタントです。(Japanese ↔ Thai)
            翻訳したい文章: "{user_text_escaped}"
            
            ミッション: この文章を3つのレベル（丁寧さ）に分けて翻訳し、日本人がタイ語を使う（またはタイ語を選ぶ）ためのドラフトを作成してください。
            1. 文章が日本語の場合: タイ語に3つのレベルで翻訳し、[カタカナ発音] と 日本語での簡単な解説を付け加えてください。
               - casual: カジュアル（同僚向け）
               - polite: 丁寧（「クラップ/カー」を含む）
               - business: ビジネス（敬語、メール、取引先向け）※丁寧と同じ場合は同じ内容で可。
            2. 文章がタイ語の場合: 日本語に3つのレベルで翻訳してください。
            
            JSON形式のみで返答してください (ダブルクォーテーション (") は \" でエスケープし、改行には \n を使用してください):
            {{
                "casual": "タイ語翻訳 [カタカナ発音] (日本語でのごく短い解説)",
                "polite": "タイ語翻訳 [カタカナ発音]",
                "business": "タイ語翻訳 [カタカナ発音]"
            }}
            '''
    result = call_gemini_api(prompt_text, require_json=True)

    

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

    text_input = request.form.get('text_input')

    ui_lang = request.form.get('ui_lang', 'th')

    if not text_input:

        return jsonify({"error": "No text provided"}), 400



    if ui_lang == 'th':

        src_lang = "ภาษาญี่ปุ่น"

        dst_lang = "ภาษาไทย"

    else:

        src_lang = "ภาษาไทย"

        dst_lang = "ภาษาญี่ปุ่น"



    # สร้าง Prompt แบบเข้มงวดสำหรับการแปลและคงเอกสาร
    prompt_text = (
        f"คุณคือผู้แปลเอกสารระดับมืออาชีพ ภารกิจคือการแปลจาก {src_lang} เป็น {dst_lang} แบบคำต่อคำและบรรทัดต่อบรรทัด\n\n"
        "⚠️ กฎเหล็กที่ต้องปฏิบัติตามอย่างเคร่งครัด ⚠️\n"
        "1. รักษารูปแบบ 100%: ต้องเว้นบรรทัด ย่อหน้า และจัดตำแหน่งให้เหมือนกับต้นฉบับเป๊ะๆ\n"
        "2. แปลครบ 100%: ห้ามข้าม ห้ามสรุป ห้ามตัดข้อความใดๆ ทิ้ง แม้แต่บรรทัดเดียว ทั้งวันที่, หัวเรื่อง, คำทักทาย, และคำลงท้าย ต้องแปลครบทุกบรรทัด\n"
        "3. ส่งคืนผลลัพธ์ที่เป็นคำแปลเท่านั้น: ห้ามมีคำอธิบาย ห้ามเกริ่นนำ ห้ามพูดคุยเด็ดขาด\n\n"
        "ข้อความต้นฉบับที่ต้องแปล:\n"
        "--- START ---\n"
        + text_input +
        "\n--- END ---"
    )

    

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

        # Extract sender/recipient name & structured fields from topic JSON

        sender_name = ""

        recipient_name = ""

        context_str = ""

        try:

            topic_obj = json.loads(topic)

            for key, val in topic_obj.items():

                if 'sender' in key.lower() or '\u0c9c\u0cc0\u0cc2\u0caa\u0cc1' in key.lower() or '\u0e1c\u0e39\u0e49\u0e2a\u0e48\u0e07' in key.lower():

                    sender_name = val

                elif 'recipient name' in key.lower() or '\u0e23\u0e31\u0e1a\u0e40\u0e08\u0e32\u0e30\u0e08\u0e07' in key.lower():

                    recipient_name = val

                elif val:

                    context_str += f"- {key}: {val}\n"

        except:
            context_str = str(topic)



        if reference_text:

            context_str += f"\n\nข้อมูลอ้างอิงจากเอกสารเดิม:\n{reference_text}"



        # Map doc_type keys to proper human-readable names for the AI
        DOC_TYPE_NAMES = {
            "weekly_report": "รายงานประจำสัปดาห์ (週報)",
            "nippou": "รายงานประจำวัน (日報)",
            "quality_claim": "หนังสือแจ้งข้อร้องเรียนคุณภาพ (クレームレター)",
            "email_task_done": "อีเมลแจ้งเสร็จงาน (業務完了メール)",
            "email_action_taken": "อีเมลแจ้งดำเนินการแล้ว (対応完了メール)",
            "email_follow_up": "อีเมล Follow-up ติดตามงาน (確認メール)",
            "email": "อีเมลธุรกิจทั่วไป (ビジネスメール)",
            "leave_request": "ใบขอลาป่วย/ลากิจ (休暇申請メール)",
            "reimbursement": "ใบเบิกค่าใช้จ่าย (経費精算書)",
            "request_equip": "ใบขอเบิกอุปกรณ์ (物品請求書)",
            "repair": "ใบแจ้งซ่อม (修理依頼書)",
        }
        doc_type_display = DOC_TYPE_NAMES.get(doc_type, doc_type)

        ui_lang = data.get('ui_lang', 'th')
        sender_line = f"ผู้ส่ง: {sender_name}" if sender_name else ""
        recipient_name_line = f"ชื่อผู้รับ: {recipient_name}" if recipient_name else ""
        date_line = f"วันที่: {date_val}" if date_val else ""

        if ui_lang == 'th':
            target_lang = "ภาษาญี่ปุ่นทางการ (Business Japanese)"
            # Specify exact Japanese business email structure
            format_rules = """
        โครงสร้างที่ถูกต้องของอีเมลธุรกิจญี่ปุ่น (ห้ามเปลี่ยนลำดับ):
        [วันที่ เช่น 2026年3月24日]
        [ชื่อผู้รับ]様  ← ถ้าไม่มีชื่อให้ใส่ตำแหน่งแทน เช่น ご担当者
        [บรรทัดว่าง]
        件名：[หัวข้อสรุป 1 บรรทัด]
        [บรรทัดว่าง]
        いつもお世話になっております。[ชื่อผู้ส่ง/บริษัท]でございます。
        [เนื้อหาหลัก]
        [บรรทัดว่าง]
        何卒よろしくお願い申し上げます。
        [บรรทัดว่าง]
        --------------------------------------------------
        [ชื่อผู้ส่ง]
        """
        else:
            target_lang = "ภาษาไทยทางการ (Formal Thai)"
            format_rules = """
        โครงสร้างที่ถูกต้องของเอกสารภาษาไทยทางการ:
        [วันที่]
        เรื่อง: [หัวข้อ]
        เรียน [ชื่อผู้รับ/ตำแหน่ง]
        [เนื้อหา]
        ขอแสดงความนับถือ
        [ชื่อผู้ส่ง] ← อยู่ด้านล่างสุดเท่านั้น
        """

        prompt_text = f"""
        คุณคือผู้ช่วยร่างเอกสารธุรกิจระดับมืออาชีพ
        ภารกิจ: ร่าง {doc_type_display}

        ข้อมูลเอกสาร:
        {date_line}
        ประเภทผู้รับ: {recipient}
        {recipient_name_line}
        {sender_line}

        เนื้อหา/วัตถุประสงค์:
        {context_str}

        ข้อกำหนด:
        1. ร่างเอกสารเป็น {target_lang} เท่านั้น ห้ามตอบกลับภาษาอื่น
        2. ใช้คำพูดระดับ Keigo (ภาษาสุภาพธุรกิจ) — ห้ามใช้คำ casual หรือ informal
        3. ถ้ามีชื่อผู้รับ ให้ใช้ชื่อจริง ห้ามใช้ [ชื่อ] หรือ [Placeholder] แทนชื่อ
        4. หากในเนื้อหามีการระบุวันที่ที่ไม่มี "ปี" (เช่น 24 มี.ค.) ให้ AI เติม "ปี" เข้าไปให้อัตโนมัติ โดยอ้างอิงจากปีของ "วันที่ของเอกสาร" เป็นหลัก
        {format_rules}

        คำเตือน: ตอบกลับเฉพาะเนื้อหาเอกสารเพียวๆ ห้ามมีคำนำ เช่น 'นี่คือร่างเอกสาร' หรือ 'ต่อไปนี้คือ...' นำหน้า
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



        ui_lang = data.get('ui_lang', 'th')

        if ui_lang == 'th':

            explain_lang = "อธิบายความหมายด้วยคำง่ายๆ เป็นภาษาไทย 1 บรรทัด"

        else:

             explain_lang = "อธิบายความหมายด้วยคำง่ายๆ เป็นภาษาญี่ปุ่น (Japanese) 1 บรรทัด"



        prompt_text = f"""

        คุณคือพจนานุกรมคำศัพท์เทคนิคอุตสาหกรรมไม้ (เครื่องจักร, งานไม้, ออฟฟิศและบริหารโรงงาน)

        คำที่ต้องการค้นหา: "{term}"



        ภารกิจ: แปลคำนี้สลับภาษา (ไทย ↔ ญี่ปุ่น) พร้อมยกตัวอย่าง

        

        ตอบกลับเป็น JSON เท่านั้น (หนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \" และใช้ \n สำหรับขึ้นบรรทัดใหม่):

        {{

            "term_main": "คำค้นหาต้นฉบับ",

            "term_target": "คำแปลเป้าหมายที่ดีที่สุด 1 คำ",

            "reading": "คำอ่านของคำศัพท์ (Romaji สำหรับภาษาไทย, หรือ Hiragana สำหรับภาษาญี่ปุ่น เริ่มด้วยวงเล็บ [ ])",

            "definition": "{explain_lang}",

            "example_jp": "ตัวอย่างประโยคภาษาญี่ปุ่น (บังคับต้องมีคำอ่าน Romaji กำกับไว้ท้ายประโยคเสมอ เช่น ... [romaji])",

            "example_th": "ตัวอย่างประโยคแปลไทย"

        }}

        """



        result = call_gemini_api(prompt_text, require_json=True)

        

        if isinstance(result, dict) and "error" in result:

            status_code = 429 if "429" in str(result.get("error")) else 500

            return jsonify(result), status_code



        parsed_data = try_extract_json(result)

        if parsed_data:

            return jsonify(parsed_data)

        else:

            return jsonify({"error": "ไม่สามารถแปลงรูปแบบพจนานุกรมได้ครับ", "ai_response": str(result)[:50]}), 500



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



        ui_lang = data.get('ui_lang', 'th')

        if ui_lang == 'th':

            system_role = "คุณคือผู้เชี่ยวชาญด้านภาษาญี่ปุ่นและระดับความสุภาพ (Keigo) อ้างอิงมาตรฐาน Bunkacho"

            explain_lang = "ภาษาไทย"

            target_lang = "ภาษาญี่ปุ่น"

        else:

            system_role = "คุณคือผู้เชี่ยวชาญด้านภาษาไทยและมารยาททางสังคม รวมถึงระดับความสุภาพ (เช่น การใช้หางเสียง ครับ/ค่ะ) อ้างอิงบริบทการทำงานในบริษัท"

            explain_lang = "ภาษาญี่ปุ่น (Japanese)"

            target_lang = "ภาษาไทย"



        prompt_text = f'''

        {system_role}

        จงวิเคราะห์ประโยคนี้: "{text.replace('"', '\"')}"

        สำหรับผู้รับสารที่เป็น: "{recipient}"

        

        ตอบกลับมาเป็น JSON (หนีสัญลักษณ์เครื่องหมายคู่ (") ด้วย \" และใช้ \n สำหรับขึ้นบรรทัดใหม่):

        {{

            "original_text": "{text}",

            "analysis": "วิเคราะห์ข้อผิดพลาดหรือจุดที่ควรปรับปรุง (เขียนอธิบายด้วย{explain_lang}ให้ชัดเจน)",

            "suggestion": "ประโยคที่แนะนำให้ใช้ที่ถูกต้องและสุภาพ ({target_lang})",

            "explanation": "คำอธิบายไวยากรณ์และความสุภาพเพิ่มเติม (เขียนอธิบายด้วย{explain_lang})"

        }}

        '''



        result = call_gemini_api(prompt_text, require_json=True)

        

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





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)