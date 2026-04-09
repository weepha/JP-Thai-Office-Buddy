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

def clean_extracted_text(text, max_chars=6000):
    """Clean up PDF-extracted text: collapse blank lines, strip trailing spaces, limit length."""
    lines = text.splitlines()
    cleaned = []
    prev_blank = False
    for line in lines:
        stripped = line.rstrip()
        is_blank = (stripped == '')
        if is_blank and prev_blank:
            continue  # Skip consecutive blank lines
        cleaned.append(stripped)
        prev_blank = is_blank
    result = '\n'.join(cleaned).strip()
    return result[:max_chars]  # Limit to avoid token overload

def get_api_keys():
    """Loads and filters valid Gemini API keys from .env file."""
    load_dotenv(override=True)
    keys = [os.getenv("GEMINI_API_KEY")] + [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]
    return [k.strip() for k in keys if k and not any(p in k for p in ["ใส่_คีย์", "ใส่_API", "YOUR_API"])]

def call_gemini_api(prompt, require_json=False, ui_lang='th'):
    """Centralized function to call Gemini API with model and key fallback."""
    current_keys = get_api_keys()
    if not current_keys:
        return {"error": "ไม่พบ API Key ในระบบครับ กรุณาเปิดไฟล์ .env แล้วใส่ GEMINI_API_KEY ก่อนใช้งานครับ" if ui_lang == 'th' else "APIキーが見つかりません。.envファイルにGEMINI_API_KEYを設定してください。"}
        
    last_error_data = {"error": "ไม่สามารถติดต่อ AI ได้ในขณะนี้" if ui_lang == 'th' else "現在AIに接続できません。"}
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
                        last_error_data = {"error": "AI Safety Block: ปัญญาประดิษฐ์ปฏิเสธการตอบเนื่องจากนโยบายความปลอดภัย" if ui_lang == 'th' else "AI Safety Block: 安全ポリシーのため、AIが応答を拒否しました。"}
                        continue

                    if 'content' in cand and 'parts' in cand['content']:
                        text = cand['content']['parts'][0].get('text', '').strip()
                        if text:
                            return text
                        else:
                            continue # Try next key/model if text is empty
                    continue
                
                elif response.status_code == 429:
                    # Always try next key on any 429 rate limit, regardless of message content
                    last_error_data = {"error": "⚠️ โควต้า AI เต็มชั่วคราวครับ กำลังลองเปลี่ยน Key สำรอง..." if ui_lang == 'th' else "⚠️ AIクォータ上限のため、予備キーに切り替えます..."}
                    continue
                
                elif response.status_code == 503:
                    last_error_data = {"error": "503 Server Error: เซิร์ฟเวอร์ AI ล่มหรือมีคนใช้งานเยอะเกินไป (High Demand) กรุณาลองกดใหม่อีกครั้งครับ" if ui_lang == 'th' else "503 エラー: AIサーバーが混み合っています（High Demand）。もう一度お試しください。"}
                    continue

                last_error_data = {"error": f"AI Error: {res_json.get('error', {}).get('message', 'Unknown')}"}
            except requests.exceptions.Timeout:
                # Handle timeout specifically for better UX
                last_error_data = {"error": "Timeout Error: ระบบ AI ใช้เวลาประมวลผลนานเกินไป (เกิน 60 วินาที) กรุณาลองใหม่อีกครั้งครับ" if ui_lang == 'th' else "タイムアウト: AIの処理時間が長すぎます。もう一度お試しください。"}
                continue
            except Exception as e:
                err_str = str(e)
                if "Read timed out" in err_str or "timeout" in err_str.lower():
                    last_error_data = {"error": "Timeout Error: ระบบ AI ใช้เวลาประมวลผลนานเกินไป กรุณาลองใหม่อีกครั้งครับ" if ui_lang == 'th' else "タイムアウト: AIの処理時間が長すぎます。もう一度お試しください。"}
                else:
                    last_error_data = {"error": f"Connection Error: {err_str}"}
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
            - ห้ามผสมภาษาในคำตอบเด็ดขาด
            - ให้คำตอบเดียวที่ดีและเป็นธรรมชาติที่สุด ห้ามทำเป็นลิสต์หรือหลายตัวเลือก
            - ถ้าแปลเป็นภาษาญี่ปุ่น: ใส่คำอ่าน Romaji แยกใน field "business_reading" (ภาษาพิมพ์โรมัน เช่น Subarashii)
            - ถ้าแปลเป็นภาษาไทย: ใส่ "-" ใน business_reading
            - ใส่ "casual" และ "polite" ว่า "โหมดอ่านจับใจความ" และ "-" ตามลำดับ (ค่าคงที่)

            ตอบกลับเป็น JSON เท่านั้น:
            {{ "casual": "โหมดอ่านจับใจความ", "polite": "-", "business": "คำแปลที่ดีที่สุด (ตัวอักษรเท่านั้น ไม่มีคำอ่าน)", "business_reading": "Romaji หรือ -" }}
            '''
        else:
            prompt_text = f'''
            คุณคือผู้ช่วยแปลภาษาอัจฉริยะ (Thai ↔ Japanese) สำหรับคนไทยที่ต้องการนำไปใช้งาน
            ข้อความที่ต้องการแปล: "{user_text_escaped}"

            ขั้นตอน:
            1. ตรวจสอบภาษาของ input ก่อน:
               - input เป็นภาษาไทย → แปลเป็นภาษาญี่ปุ่น 3 ระดับ (ห้ามใส่คำอ่านในตัวข้อความ)
               - input เป็นภาษาญี่ปุ่น → แปลเป็นภาษาไทย 3 ระดับ (ห้ามใส่คำอ่านในตัวข้อความ)

            กฎเหล็กของ output:
            - Field casual/polite/business: ตัวอักษรเท่านั้น ห้ามใส่ [คำอ่าน] ในนั้น
            - Field casual_reading/polite_reading/business_reading:
              * ถ้าผลลัพธ์เป็นภาษาญี่ปุ่น → ใส่คำอ่าน Romaji (เช่น Atsui desu)
              * ถ้าผลลัพธ์เป็นภาษาไทย → ใส่ "-"

            ตอบกลับเป็น JSON เท่านั้น:
            {{ "casual": "ระดับเป็นกันเอง", "casual_reading": "Romaji หรือ -", "polite": "ระดับสุภาพ", "polite_reading": "Romaji หรือ -", "business": "ระดับทางการ", "business_reading": "Romaji หรือ -" }}
            '''
    else:  # ui_lang == 'jp'
        if not is_draft_mode:
            prompt_text = f'''
            あなたはプロのビジネス翻訳者です。（タイ語 ↔ 日本語）日本人ユーザー向けです。
            翻訳したい文章: "{user_text_escaped}"

            厳守ルール:
            - まず入力言語を判定する: 日本語なら→タイ語、タイ語なら→日本語
            - 出力に複数の言語を混在させない。
            - 最も自然な翻訳を「1つだけ」"business" フィールドに記載（読み仮名・カタカナ読みをテキストに含めない）。
            - タイ語に翻訳する場合: 読み方をカタカナで "business_reading" フィールドに別記する（例: サワッディー・クラップ）
            - 日本語に翻訳する場合: "business_reading" は "-" とする。
            - "casual" フィールドは "意訳・要約モード" と記載（固定値）。

            JSON形式のみで返答してください:
            {{ "casual": "意訳・要約モード", "polite": "-", "business": "最適な翻訳テキストのみ", "business_reading": "カタカナ読みまたは-" }}
            '''
        else:
            prompt_text = f'''
            あなたは高度なAI翻訳アシスタントです。（タイ語 ↔ 日本語）
            翻訳したい文章: "{user_text_escaped}"

            手順:
            1. まず入力言語を判定する:
               - 日本語の場合 → タイ語に3レベルで翻訳（テキスト本文には読みを含めない）
               - タイ語の場合 → 日本語に3レベルで翻訳（テキスト本文には読みを含めない）

            ★ タイ語3レベルの厳格な定義（日本語→タイ語の場合）:
               - casual  : 友達同士の口語。ครับ/ค่ะ なし。例: ไง, เจ๋ง, โอเค
               - polite  : 日常の丁寧語。ครับ/ค่ะ を必ず付ける。例: สวัสดีครับ, ขอบคุณครับ
               - business: 職場・取引先向けの改まった表現。敬語・丁寧な接続詞を使う。例: สวัสดีครับ พร้อมคำแสดงความเคารพ, ขอแสดงความนับถือ
               ※ 「หวัดดี」は casual レベルのみ。polite や business には絶対に使用しない。

            ★ 日本語3レベルの厳格な定義（タイ語→日本語の場合）:
               - casual  : 友達口語。例: やあ, ありがと, おk
               - polite  : 日常丁寧語。例: こんにちは, ありがとうございます
               - business: ビジネス敬語(Keigo)。例: お世話になっております, よろしくお願いいたします

            出力の厳守ルール:
            - 各フィールド（casual/polite/business）は単一言語・テキストのみ。
            - タイ語翻訳の場合: casual_reading/polite_reading/business_reading にカタカナ読みを別記する。
            - 日本語翻訳の場合: casual_reading/polite_reading/business_reading は "-" とする。

            JSON形式のみで返答してください:
            {{ "casual": "カジュアル", "casual_reading": "カタカナまたは-", "polite": "丁寧", "polite_reading": "カタカナまたは-", "business": "ビジネス", "business_reading": "カタカナまたは-" }}
            '''
            
    result = call_gemini_api(prompt_text, require_json=True, ui_lang=ui_lang)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
        
    parsed_data = try_extract_json(result)
    return jsonify(parsed_data) if parsed_data else jsonify({"error": "AI Response Error", "raw": result}), 500

@app.route('/verify_content', methods=['POST'])
def verify_content():
    try:
        text_input = request.form.get('text_input')
        ui_lang = request.form.get('ui_lang', 'th')
        if not text_input:
            return jsonify({"error": "No text provided"}), 400

        if ui_lang == 'th':
            # Thai user: verify Japanese doc → translate back to Thai
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
        else:
            # Japanese user: verify Thai doc → translate back to Japanese
            prompt_text = (
                "あなたは逐語翻訳の専門家です。以下のタイ語の文書を、最初から最後まで完全に日本語に翻訳してください。\n"
                "厳守ルール:\n"
                "1. 文書の最後の一文字まで翻訳すること。途中で止めないこと。\n"
                "2. 挨拶、日付、署名など、すべての行を翻訳すること。\n"
                "3. 文書の構造（宛先・件名・本文・署名）を保持すること。\n"
                "4. 区切り線（----）はそのまま保持すること。\n"
                "5. 要約・省略は一切不可。内容の正確性確認のため、すべての語句が重要です。\n"
                "6. 翻訳結果のみを返答すること。説明は不要。\n\n"
                f"原文（タイ語）:\n\n{text_input}"
            )

        result = call_gemini_api(prompt_text, ui_lang=ui_lang)
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
                    reference_text = clean_extracted_text(reference_text)  # Clean before sending to AI
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

        DOC_TYPE_NAMES_TH = {
            "weekly_report": "รายงานประจำสัปดาห์ (週報)",
            "nippou": "รายงานประจำวัน (日報)",
            "quality_claim": "หนังสือแจ้งข้อร้องเรียนคุณภาพ (クレームレター)",
            "email_task_done": "อีเมลแจ้งเสร็จงาน (業務完了メール)",
            "email_action_taken": "อีเมลแจ้งดำเนินการแล้ว (対応完了メール)",
            "email_follow_up": "อีเมล Follow-up (確認メール)",
            "email_general": "อีเมลธุรกิจทั่วไป (ビジネスメール)",
            "email": "อีเมลธุรกิจทั่วไป (ビジネスメール)",
            "leave_request": "ใบขอลา (休暇申請メール)",
            "reimbursement": "ใบเบิกค่าใช้จ่าย (経費精算書)",
            "request_equip": "ใบขอเบิกอุปกรณ์ (備品申請書)",
            "repair": "ใบแจ้งซ่อม/IT Support (修理依頼書)"
        }
        DOC_TYPE_NAMES_JP = {
            "weekly_report": "週報 (Weekly Report)",
            "nippou": "日報 (Daily Report)",
            "quality_claim": "品質クレームレター (Quality Claim)",
            "email_task_done": "作業完了報告メール (Task Done)",
            "email_action_taken": "対応完了報告メール (Action Taken)",
            "email_follow_up": "進捗確認メール (Follow-up)",
            "email_general": "一般ビジネスメール (General Email)",
            "email": "一般ビジネスメール (General Email)",
            "leave_request": "休暇連絡メール (Leave Request)",
            "reimbursement": "経費精算書 (Reimbursement)",
            "request_equip": "備品申請書 (Equipment Request)",
            "repair": "修理・ITサポート依頼書 (Repair/IT)"
        }

        ui_lang = data.get('ui_lang', 'th')
        DOC_TYPE_NAMES = DOC_TYPE_NAMES_JP if ui_lang == 'jp' else DOC_TYPE_NAMES_TH
        doc_type_display = DOC_TYPE_NAMES.get(doc_type, doc_type)

        # Per-document-type logical constraints to prevent AI from generating
        # contextually incorrect content (e.g. "returned to work" in a leave request)
        doc_type_rules_th = {
            "leave_request": (
                "- นี่คือ 'หนังสือแจ้งขอลา' ที่เขียน **ขณะที่ยังลาอยู่หรือกำลังจะลา** "
                "ห้ามเขียนประโยคว่า 'กลับมาทำงานแล้ว' หรือ 'หายดีแล้ว' เด็ดขาด "
                "ประโยคปิดควรเป็นการขอความกรุณาอนุมัติ หรือแจ้งให้ทราบเท่านั้น"
            ),
            "reimbursement": (
                "- นี่คือ 'ใบเบิกค่าใช้จ่าย' ห้ามเพิ่มข้อมูลจำนวนเงินหรือรายการที่ไม่มีใน context "
                "ใช้เฉพาะข้อมูลที่ได้รับเท่านั้น"
            ),
            "quality_claim": (
                "- นี่คือ 'หนังสือเคลมคุณภาพ' ให้เขียนในเชิงข้อเท็จจริง ชัดเจน ไม่ใช้ภาษาก้าวร้าว "
                "แต่ต้องระบุปัญหาครบถ้วน"
            ),
        }
        doc_type_rules_jp = {
            "leave_request": (
                "- これは「休暇申請メール」です。**現在または近日中に休暇を取る旨を伝える文書**です。"
                "「職場に復帰しました」「回復しました」などの文を絶対に書かないこと。"
                "締めの文は承認のお願いまたは通知のみにすること。"
            ),
            "reimbursement": (
                "- これは「経費精算書」です。contextにない金額・品目を追加しないこと。"
                "受け取った情報のみを使用すること。"
            ),
            "quality_claim": (
                "- これは「品質クレームレター」です。事実に基づき明確に記述し、攻撃的な表現は避けること。"
                "ただし問題点は漏れなく記載すること。"
            ),
        }

        if ui_lang == 'th':
            extra_rule = doc_type_rules_th.get(doc_type, "")
            extra_rule_str = f"\n        {extra_rule}" if extra_rule else ""
            prompt_text = f"""
        あなたはプロのビジネス文書作成アシスタントです。タイ人ユーザー向けに日本語の正式なビジネス文書を作成します。
        文書の種類: {doc_type_display}
        日付: {date_val}
        宛先: {recipient}
        内容: {context_str}
        指示:
        - 必ず敬語（ビジネス敬語）を使用すること。
        - 文書の構造・フォーマットを保持すること（件名、宛先、本文、署名）。
        - Context内のすべての情報（名前、場所、詳細）を日本語に翻訳・変換すること。
        - タイ人名はカタカナに変換すること（例：ソムチャイ → ソムチャイ）。
        - 完成した文書のテキストのみを返答すること。説明は不要。{extra_rule_str}
        """
        else:
            extra_rule = doc_type_rules_jp.get(doc_type, "")
            extra_rule_str = f"\n        {extra_rule}" if extra_rule else ""
            prompt_text = f"""
        คุณคือผู้ช่วยร่างเอกสารธุรกิจมืออาชีพสำหรับผู้ใช้ชาวญี่ปุ่น ให้ร่างเป็นภาษาไทยทางการ
        ประเภทเอกสาร: {doc_type_display}
        วันที่: {date_val}
        ผู้รับ: {recipient}
        เนื้อหา: {context_str}
        คำแนะนำ:
        - ใช้ภาษาไทยทางการและสุภาพ เหมาะสมกับการติดต่อธุรกิจ
        - รักษาโครงสร้างเอกสาร (เรื่อง, เรียน, เนื้อหา, ขอแสดงความนับถือ)
        - แปลงข้อมูลทั้งหมดในเนื้อหาเป็นภาษาไทย รวมถึงชื่อ สถานที่ รายละเอียด
        - ชื่อภาษาญี่ปุ่นให้เขียนเป็นอักษรไทย (เช่น Tanaka → ทานากะ)
        - ตอบกลับเฉพาะตัวเอกสารที่ร่างเสร็จแล้ว ไม่ต้องอธิบายเพิ่มเติม{extra_rule_str}
        """

        
        result = call_gemini_api(prompt_text, ui_lang=ui_lang)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500

        clean_result = result.replace('**', '').replace('__', '').strip()
        return jsonify({"result": clean_result})
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

        if ui_lang == 'th':
            # Thai user: needs Romaji to read Japanese output or understand Japanese input
            prompt_text = f"""
        Role: Expert Thai-Japanese Business & Office Glossary (Thai user mode)
        Term: "{term}"
        Task: Translate and define for a Thai user.
        - Detect the language of the term.
        - Always provide the Romaji reading for the Japanese word in the "reading" field (if input is Thai, Romaji for translation; if input is JP, Romaji for input).
        - Definition and explanation must be in Thai.
        Format: JSON only (no extra text):
        {{
            "term_main": "{term}",
            "term_target": "translation",
            "reading": "Romaji reading of the Japanese word",
            "definition": "ความหมายในภาษาไทย",
            "example_jp": "ตัวอย่างประโยคภาษาญี่ปุ่น (plain text only, no Romaji in this field)",
            "example_jp_reading": "Romaji reading of example_jp",
            "example_th": "คำแปลภาษาไทยของตัวอย่าง"
        }}
        """
        else:
            # Japanese user: needs Katakana to read Thai output or understand Thai input
            prompt_text = f"""
        Role: 専門タイ語・日本語ビジネス用語集（日本人ユーザー向け）
        Term: "{term}"
        Task: 日本人ユーザー向けに翻訳・解説する。
        - 入力した単語の言語を判定する。
        - 常にタイ語のカタカナ読みを "reading" フィールドに記載すること（入力がタイ語なら入力単語の読み、入力が日本語なら翻訳後のタイ語の読み）。
        - 説明は日本語で記載する。
        Format: JSON only (no extra text):
        {{
            "term_main": "{term}",
            "term_target": "翻訳語",
            "reading": "タイ語のカタカナ読み",
            "definition": "日本語での意味・説明",
            "example_jp": "日本語の例文",
            "example_jp_reading": "タイ語例文のカタカナ読み（※example_th の読み方をカタカナで）",
            "example_th": "タイ語の例文"
        }}
        """

        result = call_gemini_api(prompt_text, require_json=True, ui_lang=ui_lang)
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
            "suggestion": "suggested polite sentence in {target_lang} (plain text only, no reading in this field)",
            "suggestion_reading": "if suggestion is Japanese: Romaji reading. If suggestion is Thai: Katakana reading. Otherwise: -",
            "explanation": "grammar explanation in {explain_lang}"
        }}
        '''
        result = call_gemini_api(prompt_text, require_json=True, ui_lang=ui_lang)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 500
            
        parsed_data = try_extract_json(result)
        return jsonify(parsed_data) if parsed_data else jsonify({"error": "Parse Error"}), 500
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)