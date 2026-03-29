import os
import json
import re
import requests
from pypdf import PdfReader
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Initialize Flask app
load_dotenv()
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB for safety
CORS(app)

@app.errorhandler(500)
def handle_500(e):
    # Try to detect lang from request
    lang = "th"
    try:
        if request.is_json:
            lang = request.json.get('ui_lang', 'th')
        else:
            lang = request.form.get('ui_lang', 'th')
    except: pass
    
    error_msg = str(e) if e else ""
    if lang == 'jp':
        msg = f"💡 システムエラーが発生しました: {error_msg} (テキストを短くするか、PDFを外してみてください)"
    else:
        msg = f"💡 ระบบประมวลผลข้อเสนอปัญหานี้ไม่ได้ชั่วคราว: {error_msg} (กรุณาลองลดจำนวนข้อความหรือถอดไฟล์ PDF ออกครับ)"
    return jsonify({"error": msg}), 500

# --- Helper Functions ---

def try_extract_json(text):
    """Extracts JSON from AI response text within { ... } blocks."""
    try:
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        clean_json = text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception:
        return None

def get_api_keys():
    """Loads and filters valid Gemini API keys from .env file."""
    load_dotenv(override=True)
    keys = [os.getenv("GEMINI_API_KEY")] + [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]
    return [k.strip() for k in keys if k and not any(p in k for p in ["ใส่_คีย์", "ใส่_API", "YOUR_API"])]

def call_gemini_api(prompt, require_json=False):
    """Centralized function to call Gemini API with model and key fallback."""
    current_keys = get_api_keys()
    if not current_keys:
        return {"error": "ไม่พบ API Key ในระบบครับ กรุณาเปิดไฟล์ .env แล้วใส่ GEMINI_API_KEY ก่อนใช้งานครับ"}
        
    last_error_data = {"error": "ไม่สามารถติดต่อ AI ได้ในขณะนี้"}
    models_to_try = ["gemini-2.0-flash", "gemini-flash-latest"]
    
    # Safety settings to prevent accidental blocks of business Japanese (Keigo)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    for model_name in models_to_try:
        for key in current_keys:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                gen_config = {
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 4096,
                }
                if require_json:
                    gen_config["responseMimeType"] = "application/json"
                
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}], 
                    "generationConfig": gen_config,
                    "safetySettings": safety_settings
                }
                
                response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=30)
                res_json = response.json()
                
                if response.status_code == 200:
                    candidates = res_json.get('candidates', [])
                    if not candidates:
                         continue

                    cand = candidates[0]
                    # Check finish reason
                    finish_reason = cand.get('finishReason', '')
                    if finish_reason == 'SAFETY':
                        last_error_data = {"error": "AI Safety Block: ปัญญาประดิษฐ์ปฏิเสธการตอบเนื่องจากนโยบายความปลอดภัย (Safety Filter)"}
                        continue

                    if 'content' in cand and 'parts' in cand['content']:
                        text = cand['content']['parts'][0].get('text', '').strip()
                        if text:
                            return text
                        else:
                            continue # Try next key/model if text is empty
                    continue
                
                elif response.status_code == 429:
                    msg = res_json.get('error', {}).get('message', '')
                    if "quota" in msg.lower() and len(current_keys) > 1:
                        continue 
                    return {"error": "429: ⚠️ โควต้าฟรีเต็มชั่วคราวครับ กรุณาลองใหม่ภายหลังหรือเพิ่ม API Key สำรอง"}
                
                last_error_data = {"error": f"AI Error: {res_json.get('error', {}).get('message', 'Unknown')}"}
            except Exception as e:
                last_error_data = {"error": f"Connection Error: {str(e)}"}
                continue
            
    return last_error_data

# --- Routes ---

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
    is_draft_mode = (trans_mode == 'draft')
    
    if ui_lang == 'th':
        if not is_draft_mode:
            prompt_text = f'''
            คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese) สำหรับคนไทย
            ข้อความที่ต้องการแปล: "{user_text_escaped}"

            กฎเหล็ก:
            - ตรวจสอบก่อนว่า input เป็นภาษาอะไร: ถ้าเป็นภาษาญี่ปุ่น → แปลเป็นภาษาไทย, ถ้าเป็นภาษาไทย → แปลเป็นภาษาญี่ปุ่น
            - ห้ามผสมภาษาในคำตอบเด็ดขาด เช่น ห้ามใช้ "タイ ครับ/ค่ะ" หรือ "タイ [ไทย]"
            - ให้คำตอบเดียวที่ดีและเป็นธรรมชาติที่สุด ห้ามทำเป็นลิสต์หรือหลายตัวเลือก
            - ถ้าแปลเป็นภาษาญี่ปุ่น: ใส่คำอ่าน Romaji ในวงเล็บ [ ] ต่อท้าย เช่น 素晴らしい [Subarashii]
            - ถ้าแปลเป็นภาษาไทย: ไม่ต้องใส่คำอ่าน พิมพ์แค่คำแปลเท่านั้น
            - ใส่ช่อง "casual" ว่า "โหมดอ่านจับใจความ" (ค่าคงที่)

            ตอบกลับเป็น JSON เท่านั้น:
            {{ "casual": "โหมดอ่านจับใจความ", "polite": "-", "business": "คำแปลที่ดีที่สุด" }}
            '''
        else:
            prompt_text = f'''
            คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese) สำหรับคนไทยที่ต้องการนำไปใช้งาน
            ข้อความที่ต้องการแปล: "{user_text_escaped}"

            ขั้นตอน:
            1. ตรวจสอบภาษาของ input ก่อน:
               - input เป็นภาษาไทย → แปลเป็นภาษาญี่ปุ่น 3 ระดับ พร้อมคำอ่าน [Romaji]
               - input เป็นภาษาญี่ปุ่น → แปลเป็นภาษาไทย 3 ระดับ เพื่ออ่านทำความเข้าใจ

            กฎเหล็กของ output:
            - แต่ละช่อง (casual/polite/business) ต้องมีภาษาเดียวกัน ห้ามผสม
            - ผลลัพธ์ญี่ปุ่น → ต้องเป็นญี่ปุ่นล้วน พร้อม [Romaji]
            - ผลลัพธ์ไทย → ต้องเป็นไทยล้วน ไม่มีญี่ปุ่นปน

            ตอบกลับเป็น JSON เท่านั้น:
            {{ "casual": "ระดับเป็นกันเอง", "polite": "ระดับสุภาพ", "business": "ระดับทางการ/ธุรกิจ" }}
            '''
    else:  # ui_lang == 'jp'
        if not is_draft_mode:
            prompt_text = f'''
            あなたはプロのビジネス翻訳者です。（タイ語 ↔ 日本語）日本人ユーザー向けです。
            翻訳したい文章: "{user_text_escaped}"

            厳守ルール:
            - まず入力言語を判定する: 日本語なら→タイ語、タイ語なら→日本語
            - 出力に複数の言語を混在させない。
            - 最も自然な翻訳を「1つだけ」"business" フィールドに記載。
            - タイ語に翻訳する場合: 読み方（カタカナ）を [ ] 内に必ず付ける。
            - 日本語に翻訳する場合: 読み仮名不要。
            - "casual" フィールドは "意訳・要約モード" と記載（固定値）。

            JSON形式のみで返答してください:
            {{ "casual": "意訳・要約モード", "polite": "-", "business": "最適な翻訳 1 つ" }}
            '''
        else:
            prompt_text = f'''
            あなたは高度なAI翻訳アシスタントです。（タイ語 ↔ 日本語）
            翻訳したい文章: "{user_text_escaped}"

            手順:
            1. まず入力言語を判定する:
               - 日本語の場合 → タイ語に3レベルで翻訳（[カタカナ読み] を付ける）
               - タイ語の場合 → 日本語に3レベルで翻訳（日本語のみ）

            出力の厳守ルール:
            - 各フィールド（casual/polite/business）は単一言語のみ。
            - タイ語翻訳: 「タイ語のみ＋[カタカナ読み]」。
            - 日本語翻訳: 「日本語のみ」。

            JSON形式のみで返答してください:
            {{ "casual": "カジュアル", "polite": "丁寧", "business": "ビジネス" }}
            '''
            
    result = call_gemini_api(prompt_text, require_json=True)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
        
    parsed_data = try_extract_json(result)
    return jsonify(parsed_data) if parsed_data else jsonify({"error": "AI Response Error", "raw": result}), 500

@app.route('/verify_content', methods=['POST'])
def verify_content():
    try:
        text_input = request.form.get('text_input')
        if not text_input:
            return jsonify({"error": "No text provided"}), 400

        # Verification always goes from Japanese back to Thai for clarity
        prompt_text = (
            "You are a verbatim translator. Translate the following Japanese document into Thai COMPLETELY from start to finish.\n"
            "STRICT RULES:\n"
            "1. DO NOT STOP until you have translated the VERY LAST CHARACTER of the input document.\n"
            "2. Translate EVERY SINGLE LINE, including formal greetings, dates, and signatures at the bottom.\n"
            "3. If there is a date (申請日) or name (氏名) at the very end, you MUST translate it.\n"
            "4. If there are dash lines (----), preserve them as separators.\n"
            "5. NO SUMMARIZATION or condensation. The user is checking accuracy, so every word matters.\n"
            "6. Respond ONLY with the translated text.\n\n"
             f"ORIGINAL DOCUMENT (JAPANESE):\n\n{text_input}"
        )
        
        # Increased max_output_tokens is already set to 4096 in call_gemini_api
        result = call_gemini_api(prompt_text)
        if isinstance(result, dict) and "error" in result:
            return result.get('error', 'AI Connection Error'), 500
            
        res_text = result.strip() if result else ""
        if res_text.startswith("```"):
            res_text = re.sub(r'^```[a-zA-Z]*\n|```$', '', res_text, flags=re.MULTILINE).strip()
        
        return res_text
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/generate_doc', methods=['POST'])
def generate_doc():
    try:
        data = request.json if request.is_json else request.form
        doc_type = data.get('type', 'email')
        recipient = data.get('recipient', 'ลูกค้า/หัวหน้า')
        date_val = data.get('date', '')
        topic = data.get('topic', '')
        
        reference_text = ""
        if 'document' in request.files:
            ref_file = request.files['document']
            if ref_file.filename.endswith(('.txt', '.md')):
                reference_text = ref_file.read().decode('utf-8')
            elif ref_file.filename.lower().endswith('.pdf'):
                try:
                    reader = PdfReader(ref_file)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            reference_text += page_text + "\n"
                except Exception as e:
                    ui_lang = data.get('ui_lang', 'th')
                    if ui_lang == 'jp':
                        err_msg = f"⚠️ このPDFファイルを読み取ることができません (Error: {str(e)})。テキスト形式か、直接入力してみてください。"
                    else:
                        err_msg = f"⚠️ ไม่สามารถอ่านข้อมูลจากไฟล์ PDF นี้ได้ครับ (Error: {str(e)}) กรุณาลองใช้ไฟล์ .txt หรือพิมพ์ข้อมูลโดยตรงแทนครับ"
                    return jsonify({"error": err_msg})
        
        if not topic and not reference_text:
             return jsonify({"error": "กรุณาระบุหัวข้อหรือแนบไฟล์ครับ"})

        # Process topic input (structured or simple string)
        context_str = ""
        try:
            topic_obj = json.loads(topic)
            for key, val in topic_obj.items():
                if val: context_str += f"- {key}: {val}\n"
        except:
            context_str = str(topic)

        if reference_text:
            context_str += f"\n\nReference Document:\n{reference_text}"

        DOC_TYPE_NAMES = {
            "weekly_report": "รายงานประจำสัปดาห์ (週報)",
            "nippou": "รายงานประจำวัน (日報)",
            "quality_claim": "หนังสือแจ้งข้อร้องเรียนคุณภาพ (クレームレター)",
            "email_task_done": "อีเมลแจ้งเสร็จงาน (業務完了メール)",
            "email_action_taken": "อีเมลแจ้งดำเนินการแล้ว (対応完了メール)",
            "email_follow_up": "อีเมล Follow-up (確認メール)",
            "email": "อีเมลธุรกิจทั่วไป (ビジネスメール)",
            "leave_request": "ใบขอลา (休暇申請メール)",
            "reimbursement": "ใบเบิกค่าใช้จ่าย (経費精算書)",
            "repair": "ใบแจ้งซ่อม (修理依頼書)"
        }
        
        doc_type_display = DOC_TYPE_NAMES.get(doc_type, doc_type)
        ui_lang = data.get('ui_lang', 'th')
        target_lang = "ภาษาญี่ปุ่นทางการ (Business Japanese)" if ui_lang == 'th' else "ภาษาไทยทางการ (Formal Thai)"
        
        prompt_text = f"""
        Draft a formal business document in {target_lang}.
        Type: {doc_type_display}
        Date: {date_val}
        Recipient: {recipient}
        Context: {context_str}
        Instructions: 
        - Use formal language (Keigo for JP if target is Japanese, and formal Thai if target is Thai).
        - Preserve document structure and formatting.
        - IMPORTANT: Translate ALL information in the Context (including names, locations, and details) into {target_lang}.
        - For Thai names in a Japanese document, convert them to Katakana (e.g., Somchai -> ソムチャイ).
        - For Japanese names in a Thai document, convert them to Thai phonetics (e.g., Tanaka -> ทานากะ).
        - Respond with ONLY the finalized document text.
        """
        
        result = call_gemini_api(prompt_text)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500
            
        # Support for streaming if requested via query param
        if request.args.get('stream') == 'true':
            from flask import Response
            return Response(call_gemini_api_stream(prompt_text), mimetype='text/event-stream')

        return jsonify({"result": result.strip()})
    except Exception as e:
        return jsonify({"error": f"Internal Error: {str(e)}"}), 500

@app.route('/search_glossary', methods=['POST'])
def search_glossary():
    try:
        data = request.json
        term = data.get('term', '')
        if not term: return jsonify({"error": "กรุณาระบุคำศัพท์"})

        ui_lang = data.get('ui_lang', 'th')
        explain_lang = "ภาษาไทย" if ui_lang == 'th' else "ภาษาญี่ปุ่น"

        prompt_text = f"""
        Role: Timber Industry Glossary
        Term: "{term}"
        Task: Translate and define. 
        Format: JSON only:
        {{
            "term_main": "{term}",
            "term_target": "translation",
            "reading": "[reading]",
            "definition": "definition in {explain_lang}",
            "example_jp": "example sentence [romaji]",
            "example_th": "translation"
        }}
        """
        result = call_gemini_api(prompt_text, require_json=True)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500

        parsed_data = try_extract_json(result)
        return jsonify(parsed_data) if parsed_data else jsonify({"error": "Parse Error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/analyze_politeness', methods=['POST'])
def analyze_politeness():
    try:
        data = request.json
        text = data.get('text', '')
        recipient = data.get('recipient', 'ทั่วไป')
        if not text: return jsonify({"error": "กรุณาระบุข้อความ"})

        ui_lang = data.get('ui_lang', 'th')
        explain_lang = "ภาษาไทย" if ui_lang == 'th' else "ภาษาญี่ปุ่น"
        target_lang = "ภาษาญี่ปุ่น" if ui_lang == 'th' else "ภาษาไทย"

        prompt_text = f'''
        Analyze politeness: "{text}"
        Recipient: "{recipient}"
        Response Format: JSON only:
        {{
            "original_text": "{text}",
            "analysis": "error/improvement analysis in {explain_lang}",
            "suggestion": "suggested polite sentence in {target_lang}",
            "explanation": "grammar explanation in {explain_lang}"
        }}
        '''
        result = call_gemini_api(prompt_text, require_json=True)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500
            
        parsed_data = try_extract_json(result)
        return jsonify(parsed_data) if parsed_data else jsonify({"error": "Parse Error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)