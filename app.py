import streamlit as st
import pandas as pd
import time

st.set_page_config(layout="wide")
st.title("🔎 照妖鏡模式：檢查 Google 到底給了什麼？")

# 1. 下載檔案
if "google_sheet_id" not in st.secrets:
    st.error("❌ 請設定 Secrets")
    st.stop()

sheet_id = st.secrets["google_sheet_id"]
# 加時間參數強制避開 Python 端快取
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"

st.write(f"正在從雲端下載... (ID: {sheet_id})")
try:
    xls = pd.ExcelFile(url, engine='openpyxl')
    st.success("✅ 下載成功")
except Exception as e:
    st.error(f"下載失敗: {e}")
    st.stop()

# 2. 尋找 2025-09 分頁
target_sheet = None
for name in xls.sheet_names:
    # 只要分頁名稱有 2025 且有 9，就抓出來看
    if "2025" in name and ("9" in name or "09" in name):
        target_sheet = name
        break

if target_sheet:
    st.header(f"我們讀到了分頁：[{target_sheet}]")
    
    # 3. 直接印出前 15 行，完全不處理
    st.info("👇 這是程式看到的原始資料 (前 15 列 x 前 10 欄)：")
    
    # header=None 代表不設標題，A=0, B=1... H=7
    df = pd.read_excel(xls, sheet_name=target_sheet, header=None, nrows=15)
    
    # 為了方便你看，我幫你標示出 H 欄 (Index 7)
    st.dataframe(df)
    
    st.markdown("### 👉 請檢查上面表格的第 7 直排 (欄位 7) ")
    st.write("如果在 Row 6 (第7列) 也是空的，那就代表 Google 給的檔案裡真的是空的。")
    
    # 嘗試讀取你指定的 H7 (Row 6, Col 7)
    try:
        val = df.iloc[6, 7] # 記得 Python 是從 0 開始算，所以 7 是 6
        st.metric("程式讀到 H7 (第7列 H欄) 的值為：", str(val))
    except:
        st.error("無法讀取 H7，該位置不存在。")
        
else:
    st.error("❌ 在這個 Excel 檔裡，完全找不到 2025 年 9 月的分頁！")
    st.write("目前有的分頁清單：", xls.sheet_names)
    st.warning("結論：Google 給的是舊檔案，請去試算表按「停止發布」再「重新發布」。")
