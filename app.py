import streamlit as st
import pandas as pd
import time

st.set_page_config(layout="wide")
st.title("🕵️‍♂️ 終極抓鬼模式：Google 到底給了什麼檔？")

# --- 1. 強制重新下載 (不快取) ---
try:
    if "google_sheet_id" not in st.secrets:
        st.error("❌ 請設定 Secrets")
        st.stop()
        
    sheet_id = st.secrets["google_sheet_id"]
    # 加個時間參數騙過 Google 快取
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"
    
    st.info(f"正在從雲端下載檔案... (URL ID: {sheet_id[:5]}...)")
    xls = pd.ExcelFile(url, engine='openpyxl')
    st.success("✅ 下載成功！")

except Exception as e:
    st.error(f"❌ 下載失敗: {e}")
    st.stop()

# --- 2. 顯示所有分頁名稱 ---
st.header("1. 檢查分頁清單")
all_sheets = xls.sheet_names
st.write(f"Google 給的檔案裡，總共有 {len(all_sheets)} 個分頁。")
st.write("👇 請在下面找找看，有沒有 `日報表2025-09`？")
st.code(all_sheets)

# --- 3. 針對 2025 年 9~11 月進行深度檢查 ---
st.header("2. 搜尋消失的月份")
targets = ["09", "10", "11", "9", "10", "11"]
found_sheets = []

for name in all_sheets:
    if "2025" in name:
        for t in targets:
            # 檢查是否包含 09, 9, 10...
            if f"-{t}" in name or f"{t}月" in name or t in name:
                found_sheets.append(name)

# 去除重複
found_sheets = list(set(found_sheets))

if not found_sheets:
    st.error("❌ 驚人發現：在下載的檔案中，完全找不到 2025 年 9~11 月的任何分頁！")
    st.warning("👉 這代表 Google 的「發布到網路」連結還沒更新，請去 Google 試算表按「停止發布」再「重新發布」。")
else:
    st.success(f"✅ 找到了這些疑似 9~11 月的分頁：{found_sheets}")
    
    # --- 4. 如果有找到，就把內容印出來看 ---
    st.header("3. 檢查分頁內容 (前 10 行)")
    for sheet in found_sheets:
        with st.expander(f"點此查看 [{sheet}] 的原始內容"):
            try:
                df = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=10)
                st.dataframe(df)
            except:
                st.error("讀取內容失敗")
