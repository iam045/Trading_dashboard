import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 0. UI 風格與 CSS 注入器
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; max-width: 1400px; padding-top: 2rem; }
        h1, h2, h3, p { text-align: center !important; }
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px;
            padding: 20px 15px 10px 15px; min-height: 180px;
        }
        .cal-td { height: 90px; vertical-align: top; border-radius: 10px; background-color: #fff; padding: 8px; border: 1px solid #f1f1f1; }
        .bg-green { background-color: #e0f2f1 !important; color: #004d40 !important; }
        .bg-red { background-color: #ffebee !important; color: #b71c1c !important; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return "plotly_white"

# ==========================================
# 1. 資料處理核心 (修復為名稱對應)
# ==========================================

def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    """修復版：根據 Excel 標題名稱讀取，不再依賴欄位順序"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到含有 '期望值' 的分頁"
    
    try:
        # header=14 代表標題在第 15 列
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 定義新舊欄位映射 (左邊是你的 Excel 標題，右邊是程式內變數)
        mapping = {
            '日期': 'Date',
            '損益': 'PnL',
            '標準R(盈虧比)': 'R',
            '1R單位': 'Risk_Amount',
            '期望值': 'Exp_Excel',
            '累計損益': 'Cum_PnL'
        }
        
        # 僅選取存在的欄位
        existing_cols = [col for col in mapping.keys() if col in df.columns]
        df_clean = df[existing_cols].copy()
        df_clean.rename(columns={k: v for k, v in mapping.items() if k in df_clean.columns}, inplace=True)
        
        # 若缺少策略欄位，給予預設值避免報錯
        if 'Strategy' not in df_clean.columns:
            df_clean['Strategy'] = '預設策略'

        # 數值轉型
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        for col in ['PnL', 'R', 'Risk_Amount']:
            if col in df_clean.columns:
                df_clean[col] = clean_numeric(df_clean[col])
            
        # 移除關鍵欄位為空的無效行
        df_clean = df_clean.dropna(subset=['Date', 'PnL'])
        
        # 計算累積期望值 (Running EV)
        if 'R' in df_clean.columns:
            df_clean['Running_EV'] = df_clean['R'].expanding().mean()
            
        return df_clean.sort_values('Date'), None
    except Exception as e: return None, f"數據處理失敗: {e}"

# ==========================================
# 2. 顯示與繪圖
# ==========================================

def display_expectancy_lab(xls):
    inject_custom_css()
    df, error = get_expectancy_data(xls)
    
    if error:
        st.warning(error)
        return
    if df is None or df.empty:
        st.info("資料庫目前沒有有效的交易資料。")
        return

    # 頂部 KPI 卡片
    current_ev = df['R'].mean() if 'R' in df.columns else 0
    total_r = df['R'].sum() if 'R' in df.columns else 0
    
    st.header("🧪 期望值實驗室 (R-Unit Tracking)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("交易總數", f"{len(df)} 筆")
    c2.metric("當前期望值", f"{current_ev:.3f} R")
    c3.metric("累積獲利", f"{total_r:.2f} R")
    c4.metric("平均勝率", f"{(df['PnL'] > 0).mean():.1%}")

    # 期望值變動曲線圖
    st.subheader("期望值變動趨勢 (Running EV)")
    fig_ev = px.line(df, x='Date', y='Running_EV', title="系統穩定度 (目標 > 0.2R)")
    fig_ev.add_hline(y=0, line_dash="dash", line_color="gray")
    fig_ev.add_hline(y=current_ev, line_color="red", annotation_text=f"平均: {current_ev:.3f}")
    st.plotly_chart(fig_ev, use_container_width=True)

    # 顯示原始數據表格
    with st.expander("查看底層數據 (最新 10 筆)"):
        st.dataframe(df.tail(10), use_container_width=True)

# 為了與 app.py 兼容，如果需要日曆或其他元件，可在此處補充定義
