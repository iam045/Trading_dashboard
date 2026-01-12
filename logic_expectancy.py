import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 0. 樣式注入 (對齊您的個人化色調 #81C7D4)
# ==========================================
def inject_custom_css():
    css = """
    <style>
        .stMetric { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px; }
        .stMetric:hover { border-color: #81C7D4; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ==========================================
# 1. 資料處理核心 (改用名稱對應)
# ==========================================
def get_expectancy_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到包含 '期望值' 的分頁"
    
    try:
        # header=14 代表資料從 Excel 第 15 列開始抓取
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 定義您 Excel 中的新欄位名稱對照表
        mapping = {
            '日期': 'Date',
            '損益': 'PnL',
            '標準R(盈虧比)': 'PnL_R',
            '1R單位': 'Risk_Unit',
            '期望值': 'Excel_EV',
            '累計損益': 'Cum_PnL'
        }
        
        # 只抓取存在的欄位並重新命名
        existing_cols = [col for col in mapping.keys() if col in df.columns]
        df_clean = df[existing_cols].copy()
        df_clean.rename(columns={k: v for k, v in mapping.items() if k in df_clean.columns}, inplace=True)
        
        # 資料清理與轉型
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        for col in ['PnL', 'PnL_R', 'Risk_Unit', 'Cum_PnL']:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace(',', ''), errors='coerce')
        
        df_clean = df_clean.dropna(subset=['Date', 'PnL']).sort_values('Date')
        
        # 若 Excel 中沒計算 Running EV，程式會自動根據 PnL_R 補算
        if 'PnL_R' in df_clean.columns:
            df_clean['Running_EV'] = df_clean['PnL_R'].expanding().mean()
            
        return df_clean, None
    except Exception as e:
        return None, f"Excel 讀取失敗: {e}"

# ==========================================
# 2. 顯示主函數 (名稱對齊 app.py)
# ==========================================
def display_expectancy_lab(xls):
    inject_custom_css()
    df, error = get_expectancy_data(xls)
    
    if error:
        st.error(error)
        return

    st.header("🧪 期望值實驗室 (R-Unit Based)")
    
    # 指標計算
    total_trades = len(df)
    current_ev = df['PnL_R'].mean() if 'PnL_R' in df.columns else 0
    total_r = df['PnL_R'].sum() if 'PnL_R' in df.columns else 0
    win_rate = (df['PnL'] > 0).mean()

    # KPI 卡片
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("交易次數", f"{total_trades} 筆")
    c2.metric("當前期望值", f"{current_ev:.3f} R")
    c3.metric("累積獲利 (R)", f"{total_r:.2f} R")
    c4.metric("勝率", f"{win_rate:.1%}")

    # 期望值趨勢圖 (Running EV)
    st.subheader("期望值變動趨勢 (應穩定 > 0.2R)")
    if 'Running_EV' in df.columns:
        fig_ev = px.line(df, x='Date', y='Running_EV', labels={'Running_EV': '期望值 (R)'})
        fig_ev.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_ev.add_hline(y=current_ev, line_color="red", annotation_text=f"目前: {current_ev:.3f}")
        st.plotly_chart(fig_ev, use_container_width=True)

    # 資金成長圖
    st.subheader("資金成長曲線 (累計損益)")
    if 'Cum_PnL' in df.columns:
        fig_pnl = px.area(df, x='Date', y='Cum_PnL', color_discrete_sequence=['#81C7D4'])
        st.plotly_chart(fig_pnl, use_container_width=True)
