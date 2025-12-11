import streamlit as st
import pandas as pd

def display_expectancy_lab(xls):
    """
    期望值實驗室的主邏輯：
    1. 尋找 '期望值' 分頁
    2. 顯示原始資料供欄位確認
    3. (未來) 計算勝率、賺賠比、凱利公式
    """
    st.header("🧪 期望值數據分析")
    
    # 1. 自動尋找分頁 (模糊搜尋 '期望值')
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    
    if not target_sheet:
        st.warning("⚠️ 找不到含有 '期望值' 關鍵字的分頁。")
        st.write("目前讀到的所有分頁：", xls.sheet_names)
        return

    st.success(f"✅ 成功讀取分頁：[{target_sheet}]")
    
    # 2. 讀取前 15 行原始資料
    try:
        st.info("👇 請查看下方表格，並截圖或告訴我 **「日期」、「策略」、「多空」、「損益」** 這四個欄位的準確名稱：")
        
        # header=None 代表先不設標題，直接把 Excel 的格子印出來看最準
        df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None, nrows=15)
        st.dataframe(df_raw)
        
    except Exception as e:
        st.error(f"讀取內容失敗: {e}")
