import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import io

# ดึง API Key จากระบบรักษาความปลอดภัยของเว็บ
API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=API_KEY)

def process_image_with_ai(image):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
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

st.set_page_config(page_title="ระบบดึงข้อมูลรับแจ้ง", layout="wide")
st.title("ระบบแปลงรูปภาพใบรับแจ้งเป็น Excel")

uploaded_files = st.file_uploader(
    "อัปโหลดรูปภาพใบรับแจ้ง (เลือกได้หลายรูปพร้อมกัน)", 
    type=["jpg", "png", "jpeg"], accept_multiple_files=True
)

if uploaded_files:
    if st.button("สกัดข้อมูลทั้งหมดด้วย AI", type="primary"):
        all_data = []
        my_bar = st.progress(0, text="กำลังประมวลผล...")
        
        for i, uploaded_file in enumerate(uploaded_files):
            image = Image.open(uploaded_file)
            try:
                extracted_data = process_image_with_ai(image)
                all_data.append(extracted_data)
            except Exception as e:
                st.error(f"ไฟล์ {uploaded_file.name} มีปัญหา: {e}")
            
            my_bar.progress(int(((i + 1) / len(uploaded_files)) * 100))
            
        if all_data:
            st.success("ประมวลผลเสร็จสิ้น! ตรวจสอบตัวอย่างและกดดาวน์โหลด")
            df = pd.DataFrame(all_data)
            st.dataframe(df)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='ข้อมูล')
            
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ Excel",
                data=output.getvalue(),
                file_name="ข้อมูลรับแจ้ง_อัปเดต.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
