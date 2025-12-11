import streamlit as st
import pandas as pd
import re
# 引入我們拆分出去的三個模組
from utils import load_google_sheet 
from logic_yearly import get_yearly_data_and_chart 
from logic_expectancy import display_expectancy_lab # 新增這行

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室")

# --- 2. 重新整理按鈕 ---
if st.button("🔄 重新整理數據"):
    st.cache_resource.clear()
    st.rerun()

# --- 3. 載入資料 ---
xls, err_msg = load_google_sheet()

if err_msg:
    st.error(err_msg)
    st.stop()

# --- 4. 分頁架構 ---
tab1, tab2, tab3 = st.tabs(["📊 總覽儀表板", "📅 年度戰績回顧", "🧪 期望值實驗室"])

# === Tab 1: 總覽 ===
with tab1:
    if '累積總表' in xls.sheet_names:
        try:
            # 簡易讀取總表邏輯 (為了保持 app.py 簡潔，這段未來也可以考慮拆出去)
            df_prev = pd.read_excel(xls, '累積總表', header=None, nrows=10)
            h_idx = -1
            for i, row in enumerate(df_prev.values):
                if '累積損益' in "".join([str(r) for r in row]): 
                    h_idx = i; break
            if h_idx != -1:
                df_total = pd.read_excel(xls, '累積總表', header=h_idx)
                y_col = next((c for c in df_total.columns if '累積損益' in str(c)), None)
                if y_col:
                    latest_val = df_total[y_col].iloc[-1]
                    st.metric("歷史總權益", f"${latest_val:,.0f}")
                    import plotly.express as px
                    st.plotly_chart(px.line(df_total, y=y_col, title="歷史資金成長"), use_container_width=True)
        except: pass

# === Tab 2: 年度回顧 (由 logic_yearly.py 接管) ===
with tab2:
    # 自動偵測年份
    detected_years = set()
    for name in xls.sheet_names:
        clean_name = re.sub(r"[ _－/.-]", "", str(name))
        match = re.search(r"日報表(\d{4})", clean_name)
        if match: detected_years.add(int(match.group(1)))
    target_years = sorted(list(detected_years), reverse=True) if detected_years else [2025, 2024, 2023, 2022, 2021]

    progress_bar = st.progress(0, text="數據載入中...")
    
    for i, year in enumerate(target_years):
        # 呼叫 logic_yearly
        result = get_yearly_data_and_chart(xls, year)
        
        if result:
            fig, final, high, low, mdd, m_stats = result
            
            note = " (記錄較不完整)" if year in [2021, 2022] else ""
            st.markdown(f"### {year} 年{note}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("總損益", f"${final:,.0f}") 
            c2.metric("高點", f"${high:,.0f}") 
            c3.metric("低點", f"${low:,.0f}")
            c4.metric("最大回檔 (MDD)", f"${mdd:,.0f}", delta_color="normal")
            
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"📅 {year} 各月損益：")
            st.dataframe(pd.DataFrame([m_stats]), hide_index=True, use_container_width=True)
            st.markdown("---")
            
        progress_bar.progress((i + 1) / len(target_years))
    progress_bar.empty()

# === Tab 3: 期望值實驗室 (由 logic_expectancy.py 接管) ===
with tab3:
    # 呼叫 logic_expectancy
    display_expectancy_lab(xls)
