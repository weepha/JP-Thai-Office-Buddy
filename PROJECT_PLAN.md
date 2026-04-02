# 🗺️ JP-Thai Office Buddy - Project Roadmap

เอกสารนี้สร้างขึ้นเพื่อติดตามความคืบหน้าของโปรเจกต์ (Roadmap) และบอกว่า **"ตอนนี้เราอยู่จุดไหน"** 
เมื่อคุณเปลี่ยนไปทำโปรเจกต์นี้ในคอมพิวเตอร์เครื่องอื่น ให้เข้ามาดูหัวข้อ **"📍 สถานะปัจจุบัน (Current Status)"** เป็นอันดับแรกครับ!

---

## 🎯 1. รายละเอียดโปรเจกต์ (Project Overview)
สร้างระบบ AI Assistant (ด้วย Python Flask + Gemini API) สำหรับพนักงานออฟฟิศที่ทำงานกับบริษัทญี่ปุ่น โดยมีฟีเจอร์หลักคือ:
*   แปลภาษาไทย-ญี่ปุ่น 2 โหมด (อ่านจับใจความ 1 ระดับ / แต่งประโยค 3 ระดับ)
*   แปลและตรวจสอบเนื้อหาเอกสารอย่างละเอียด (Verify Content)
*   เขียนฟอร์มเอกสาร (อีเมล, รายงาน, ใบลา, เบิกอุปกรณ์, แจ้งซ่อม) ด้วยภาษาที่เหมาะสม
*   คลังศัพท์เทคนิค (Glossary) พร้อมตัวอย่างประโยค
*   ตรวจสอบความสุภาพภาษาญี่ปุ่น (Keigo Analysis)
*   PWA (Progressive Web App) - ติดตั้งบนมือถือได้ผ่าน "Add to Home Screen"
*   รองรับ 2 ภาษา UI (ไทย / ญี่ปุ่น)

---

## 📍 2. สถานะปัจจุบัน (Current Status & Next Steps)

### ✅ เฟส 1: พัฒนาและทดสอบระบบ Backend + Frontend — **เสร็จสมบูรณ์**
- [x] รันโปรแกรมผ่าน `app.py` ได้ที่ http://127.0.0.1:5000/
- [x] ระบบแปลภาษา (2 โหมด) ทำงานถูกต้อง มีคำอ่าน Romaji/Katakana
- [x] ระบบตรวจเอกสาร (Verify Content) แปลกลับครบถ้วน แสดงใน Modal
- [x] ระบบสร้างเอกสาร (12 ประเภท) ทำงานถูกต้อง
- [x] คลังศัพท์เทคนิค ค้นหาได้ทั้งไทย-ญี่ปุ่น
- [x] Error handling ครอบคลุม (PDF error, API quota, timeout)
- [x] UI ภาษาไทย/ญี่ปุ่น switch ได้ทุก element

### ✅ เฟส 3: PWA (Progressive Web App) — **เสร็จสมบูรณ์**
- [x] `manifest.json` สร้างแล้ว
- [x] `service-worker.js` ลงทะเบียนแล้ว
- [x] icon-192.png / icon-512.png พร้อมแล้ว
- [x] ผู้ใช้สามารถกด "Add to Home Screen" บนมือถือได้

### 👉 เฟส 2: นำระบบขึ้น Cloud (Deployment) — **ยังไม่ได้ทำ**
เพื่อให้ระบบรัน 24 ชม. และไม่ต้องสั่งรัน `app.py` ด้วยตัวเองอีกต่อไป
- [ ] สมัคร Cloud Server ฟรี (แนะนำ Render.com หรือ PythonAnywhere)
- [ ] นำโค้ดชุดนี้อัปโหลดและเปิดรันบน Cloud
- [ ] จะได้ URL จริง (เช่น `https://jp-thai-buddy.onrender.com`) มาใช้งาน

---

## 🚀 3. แผนงานในอนาคต (Future Roadmap)

### เฟส 4: พัฒนาแอปผ่าน Flutter (ทางเลือกเสริม)
- [ ] หากทำจบเฟส 2 แล้วรู้สึกว่ายังอยากได้เป็นแอปมือถือลงเครื่องแบบสมบูรณ์ ให้ไปพัฒนาต่อในโฟลเดอร์ `mobile_app/`
- [ ] เขียนโค้ด Flutter เพื่อดึง API จากลิงก์ Cloud ในเฟส 2 มาใช้
- [ ] ทดสอบและ Export ออกเป็นไฟล์ APK สำหรับ Android

---

## 📝 4. บันทึกการแก้ไขสำคัญ (Changelog)
| วันที่ | การเปลี่ยนแปลง |
|--------|----------------|
| Mar 2026 | สร้าง Backend (app.py), Frontend (index.html) ครบทุกฟีเจอร์ |
| Mar 2026 | เพิ่ม PWA (manifest, service-worker, icons) |
| Mar 2026 | เพิ่ม Verify Content modal, phonetic reading subtitles |
| Mar 2026 | เพิ่ม Send Email button สำหรับ doc type อีเมล |
| Apr 2026 | แก้ bug JS (resDocsVerifyArea null ref), ลบ unused variable, แก้ modal gradient |
