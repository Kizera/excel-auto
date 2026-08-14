import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import time
import concurrent.futures
import os

# 1. ตั้งค่าหน้าเว็บและการแสดงผล
st.set_page_config(page_title="Data Extraction System", layout="wide")

# CSS ตกแต่งสไตล์ Netflix (Dark Mode & Red Accent)
st.markdown("""
    <style>
    /* ซ่อนแถบเมนูที่ไม่จำเป็น */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* บังคับโทนสีพื้นหลังและตัวอักษร */
    .stApp {
        background-color: #141414;
        color: #FFFFFF;
    }
    
    /* สไตล์ปุ่มกดหลัก (สีแดง Netflix) */
    .stButton>button {
        background-color: #E50914 !important;
        color: white !important;
        border-radius: 4px;
        height: 45px;
        font-size: 16px;
        font-weight: bold;
        border: none;
        transition: 0.2s;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #f40612 !important;
        transform: scale(1.02);
    }
    
    /* ตกแต่งสีข้อความ */
    h1, h2, h3 { color: #FFFFFF !important; font-weight: bold; }
    p { color: #B3B3B3 !important; }
    
    /* ตกแต่งสีหลอดโหลด (Progress Bar) */
    .stProgress > div > div > div > div {
        background-color: #E50914;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. ตั้งค่า API Key และไฟล์บล็อคหลัก
API_KEY = st.secrets["API_KEY"]
genai.configure(api_key=API_KEY)
MASTER_FILE = "ทะเบียนรับแจ้งอำเภอธัญบุรี_2.xlsx"

# 3. ฟังก์ชัน AI สกัดข้อมูล
def process_image_with_ai(image):
    model = genai.GenerativeModel('gemini-flash-latest')
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

# 4. สร้างแถบเมนูด้านข้าง (Sidebar)
st.sidebar.title("SYSTEM MENU")
page = st.sidebar.radio("", ["DATA EXTRACTION", "DATABASE HISTORY"])

# ==========================================
# หน้าที่ 1: DATA EXTRACTION (สกัดข้อมูล)
# ==========================================
if page == "DATA EXTRACTION":
    st.markdown("<h2 style='text-align: center;'>DATA EXTRACTION</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Upload documents for automated processing.</p>", unsafe_allow_html=True)
    st.write("---")

    uploaded_files = st.file_uploader(
        "Upload files", 
        type=["jpg", "png", "jpeg"], accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        if st.button("PROCESS DOCUMENTS"):
            total_files = len(uploaded_files)
            all_data = [None] * total_files
            
            # โครงสร้างสำหรับแสดงสถานะ
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            completed = 0
            start_time = time.time()
            max_workers = min(5, total_files)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {
                    executor.submit(process_image_with_ai, Image.open(file)): i 
                    for i, file in enumerate(uploaded_files)
                }
                
                for future in concurrent.futures.as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        data = future.result()
                        all_data[index] = data
                    except Exception as e:
                        st.error(f"Error processing file {index + 1}: {e}")
                    
                    completed += 1
                    
                    # คำนวณเปอร์เซ็นต์และเวลาประเมิน (ETA)
                    elapsed_time = time.time() - start_time
                    avg_time_per_file = elapsed_time / completed
                    remaining_files = total_files - completed
                    eta_seconds = int(avg_time_per_file * remaining_files)
                    percentage = int((completed / total_files) * 100)
                    
                    # อัปเดตข้อความสถานะ
                    status_text.markdown(
                        f"**Processing... {percentage}%** | Completed: {completed}/{total_files} | "
                        f"Estimated time remaining: {eta_seconds} seconds"
                    )
                    progress_bar.progress(percentage)
            
            valid_data = [d for d in all_data if d is not None]
            status_text.empty()
            progress_bar.empty()
            
            if valid_data:
                st.success(f"Successfully processed {len(valid_data)} documents.")
                new_df = pd.DataFrame(valid_data)
                
                # จัดการบันทึกข้อมูลลงไฟล์บล็อคหลัก
                if os.path.exists(MASTER_FILE):
                    try:
                        master_df = pd.read_excel(MASTER_FILE)
                        updated_df = pd.concat([master_df, new_df], ignore_index=True)
                        updated_df.to_excel(MASTER_FILE, index=False)
                        st.info("Data successfully appended to Master Database.")
                    except Exception as e:
                        st.error(f"Error accessing Master file: {e}")
                        updated_df = new_df
                else:
                    new_df.to_excel(MASTER_FILE, index=False)
                    updated_df = new_df
                    st.info("Created new Master Database.")
                
                # แสดงตัวอย่างเฉพาะข้อมูลที่เพิ่งเพิ่มเข้าไปใหม่
                st.markdown("### RECENT EXTRACTED DATA")
                st.dataframe(updated_df.tail(len(valid_data)), use_container_width=True, hide_index=True)

# ==========================================
# หน้าที่ 2: DATABASE HISTORY (ประวัติฐานข้อมูล)
# ==========================================
elif page == "DATABASE HISTORY":
    st.markdown("<h2 style='text-align: center;'>MASTER DATABASE</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>View and manage historical records.</p>", unsafe_allow_html=True)
    st.write("---")
    
    if os.path.exists(MASTER_FILE):
        try:
            df = pd.read_excel(MASTER_FILE)
            
            # สรุปสถิติเบื้องต้นแบบเรียบง่าย
            st.markdown(f"<p>Total records in database: <b>{len(df)}</b></p>", unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)
            
            # ปุ่มดาวน์โหลดไฟล์บล็อคหลักทั้งก้อน
            with open(MASTER_FILE, "rb") as file:
                st.download_button(
                    label="DOWNLOAD MASTER DATABASE",
                    data=file,
                    file_name=MASTER_FILE,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"Could not load database: {e}")
    else:
        st.warning("No historical data found. Please process documents to initialize the database.")
