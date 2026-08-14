import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import io
import concurrent.futures  # เพิ่มไลบรารีนี้สำหรับทำ Threading

st.set_page_config(page_title="ระบบดึงข้อมูลรับแจ้ง", layout="centered", page_icon="📄")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 45px;
        font-size: 16px;
        font-weight: bold;
        transition: 0.3s;
    }
    </style>
    """, unsafe_allow_html=True)

API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=API_KEY)

def process_image_with_ai(image):
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = """
    ดึงข้อมูลจากรูปภาพใบรับแจ้งนี้ และส่งออกเป็นรูปแบบ JSON เท่านั้น
    โดยใช้โครงสร้าง Key ดังนี้:
    {
      "วันเดือนปี": "", "ลำดับ": "", "เวลา": "", "แหล่งข้อมูล": "",
      "ชื่อ - สกุล": "", "อายุ": "", "อาชีพ": "", "ที่อยู่": "",
      "ตำบล": "", "เบอร์โทร": "", "โรค": "", "วันที่เริ่มป่วย": "",
      "วันที่เข้ารับการรักษา": "", "ประเภทการรักษา": ""
    }
    เงื่อนไข:
    1. ลำดับ และ เวลา ให้ปล่อยเป็นค่าว่าง ("") เสมอ
    2. จุดไหนที่ลายมืออ่านไม่ออก ให้ใส่ข้อความ "[รอตรวจสอบ]"
    3. ห้ามพิมพ์ข้อความอื่นนอกจาก JSON
    """
    response = model.generate_content([prompt, image])
    result_text = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(result_text)

st.markdown("<h2 style='text-align: center; color: #2e3b4e;'>📄 ระบบสกัดข้อมูลใบรับแจ้ง</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>อัปโหลดรูปภาพใบรับแจ้งเพื่อแปลงเป็น Excel อัตโนมัติ</p>", unsafe_allow_html=True)
st.write("---")

uploaded_files = st.file_uploader(
    "อัปโหลดไฟล์ที่นี่", 
    type=["jpg", "png", "jpeg"], accept_multiple_files=True,
    label_visibility="collapsed"
)

if uploaded_files:
    if st.button("✨ เริ่มสกัดข้อมูล", type="primary"):
        # จองพื้นที่ในลิสต์ไว้ให้เท่ากับจำนวนรูป เพื่อรักษาลำดับข้อมูล
        all_data = [None] * len(uploaded_files)
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        status_text.markdown(f"**กำลังประมวลผลคู่ขนาน {len(uploaded_files)} ไฟล์...** ⏳")
        completed = 0
        
        # ตั้งค่าจำนวน Worker (จำกัดที่ 3-5 เพื่อไม่ให้โดน API แบนข้อหา Rate Limit)
        max_workers = min(5, len(uploaded_files))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # ส่งงานให้ Worker ทำพร้อมกัน
            future_to_index = {
                executor.submit(process_image_with_ai, Image.open(file)): i 
                for i, file in enumerate(uploaded_files)
            }
            
            # รอดึงผลลัพธ์จากรูปที่เสร็จแล้ว
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    data = future.result()
                    all_data[index] = data  # ใส่ข้อมูลกลับไปในลำดับเดิม
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดกับไฟล์ที่ {index + 1}: {e}")
                
                # อัปเดตหลอดความคืบหน้า
                completed += 1
                progress_bar.progress(int((completed / len(uploaded_files)) * 100))
        
        # กรองเอาเฉพาะข้อมูลที่สำเร็จ (ตัด None ทิ้งกรณีมี Error)
        valid_data = [d for d in all_data if d is not None]
        
        status_text.empty()
        progress_bar.empty()
        
        if valid_data:
            st.success(f"✅ ประมวลผลเสร็จสิ้น {len(valid_data)} รายการ!")
            df = pd.DataFrame(valid_data)
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='ข้อมูล')
            
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ Excel",
                data=output.getvalue(),
                file_name="ข้อมูลรับแจ้ง_อัปเดต.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
