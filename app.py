import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import time
import numpy as np 
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室")

# --- 2. 連線設定 ---
@st.cache_resource(ttl=60) 
def load_google_sheet():
    try:
        if "google_sheet_id" not in st.secrets:
            return None, "請在 Streamlit Secrets 設定 'google_sheet_id'"
        sheet_id = st.secrets["google_sheet_id"]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"
        return pd.ExcelFile(url, engine='openpyxl'), None
    except Exception as e:
        return None, f"無法讀取雲端檔案: {e}"

# --- 3. 資料讀取 ---
def read_daily_pnl(xls, sheet_name):
    try:
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=50)
        
        # 策略 A
        header_row = -1
        pnl_col_idx = -1
        target_keywords = ['日總計', '總計', '累計損益', '損益']
        
        for r in range(len(df_raw)):
            row_values = [str(v).replace(" ", "") for v in df_raw.iloc[r]]
            if any(k in v for k in target_keywords for v in row_values):
                header_row = r
                for c, val in enumerate(row_values):
                    if any(k in val for k in target_keywords):
                        pnl_col_idx = c
                        break
                break
        
        if header_row != -1:
            df = df_raw.iloc[header_row+1:, [0, pnl_col_idx]].copy()
            df.columns = ['Date', 'Daily_PnL']
            if clean_data(df).empty == False: return clean_data(df)

        # 策略 B
        if df_raw.shape[0] > 6 and df_raw.shape[1] > 7:
            df_force = df_raw.iloc[6:, [0, 7]].copy()
            df_force.columns = ['Date', 'Daily_PnL']
            return clean_data(df_force)

        return pd.DataFrame()
    except: return pd.DataFrame()

def clean_data(df):
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Daily_PnL'] = pd.to_numeric(df['Daily_PnL'].astype(str).str.replace(',', '').str.strip(), errors='coerce')
    return df.dropna(subset=['Date', 'Daily_PnL'])

# --- 關鍵輔助函式：計算 0 軸交點 (Interpolation) ---
def insert_zero_crossings(df):
    if df.empty: return df
    df = df.sort_values('Date').reset_index(drop=True)
    new_rows = []
    
    for i in range(len(df) - 1):
        curr_row = df.iloc[i]
        next_row = df.iloc[i+1]
        y1 = curr_row['Cumulative_PnL']
        y2 = next_row['Cumulative_PnL']
        
        if (y1 > 0 and y2 < 0) or (y1 < 0 and y2 > 0):
            t1 = curr_row['Date'].timestamp()
            t2 = next_row['Date'].timestamp()
            zero_t = t1 + (0 - y1) * (t2 - t1) / (y2 - y1)
            zero_date = pd.Timestamp.fromtimestamp(zero_t)
            new_rows.append({'Date': zero_date, 'Daily_PnL': 0, 'Cumulative_PnL': 0})
            
    if new_rows:
        df_new = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df_new = df_new.sort_values('Date').reset_index(drop=True)
        return df_new
    return df

# --- 4. 繪圖邏輯 ---
def plot_yearly_trend(xls, year):
    all_data = []
    sheet_map = {re.sub(r"[ _－/.-]", "", str(name)): name for name in xls.sheet_names}
    
    for month in range(1, 13): 
        targets = [f"日報表{year}{month:02d}", f"日報表{year}{month}"]
        real_name = next((sheet_map[t] for t in targets if t in sheet_map), None)
        if real_name:
            df_m = read_daily_pnl(xls, real_name)
            if not df_m.empty: all_data.append(df_m)
    
    if not all_data: return None 

    df_year = pd.concat(all_data)
    df_year = df_year[df_year['Date'].dt.year == year]
    
    # 時間結界
    today = pd.Timestamp.now().normalize()
    df_year = df_year[df_year['Date'] <= today]

    if df_year.empty: return None

    df_year = df_year.sort_values('Date')
    df_year['Cumulative_PnL'] = df_year['Daily_PnL'].cumsum()
    
    # 統計數據
    latest_pnl = df_year['Cumulative_PnL'].iloc[-1]
    max_pnl = df_year['Cumulative_PnL'].max()
    min_pnl = df_year['Cumulative_PnL'].min()
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    monthly_stats_display = {}
    for m in range(1, 13):
        val = monthly_sums.get(m, None)
        monthly_stats_display[f"{m}月"] = f"${val:,.0f}" if val is not None else "---"

    # 插值處理
    df_plot = insert_zero_crossings(df_year)
    y_pos = df_plot['Cumulative_PnL'].apply(lambda x: x if x >= 0 else None)
    y_neg = df_plot['Cumulative_PnL'].apply(lambda x: x if x <= 0 else None)

    fig = go.Figure()

    # 紅色區域 (獲利)
    fig.add_trace(go.Scatter(
        x=df_plot['Date'], y=y_pos,
        mode='lines', name='獲利',
        line=dict(color='#ff4d4d', width=2),
        fill='tozeroy', fillcolor='rgba(255, 77, 77, 0.1)'
    ))
    
    # 綠色區域 (虧損)
    fig.add_trace(go.Scatter(
        x=df_plot['Date'], y=y_neg,
        mode='lines', name='虧損',
        line=dict(color='#00cc66', width=2),
        fill='tozeroy', fillcolor='rgba(0, 204, 102, 0.1)'
    ))

    # X 軸刻度
    tick_vals = [pd.Timestamp(f"{year}-{m:02d}-01") for m in range(1, 13)]
    tick_text = [f"{m}月" for m in range(1, 13)]
    
    for val in tick_vals:
        if val.month == 1: continue
        fig.add_vline(x=val, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    # --- 關鍵修正：徹底移除 Title ---
    fig.update_layout(
        # title=...,  <-- 這裡真的拿掉了
        margin=dict(t=10, b=10, l=10, r=10), # 上方留白縮小到 10px
        xaxis_title="", 
        yaxis_title="累計損益",
        hovermode="x unified", 
        height=450,
        showlegend=False,
        xaxis=dict(
            range=[f"{year}-01-01", f"{year}-12-31"],
            tickmode='array', tickvals=tick_vals, ticktext=tick_text
        )
    )
    
    return fig, latest_pnl, max_pnl, min_pnl, monthly_stats_display

# --- 5. 主程式 ---
tab1, tab2 = st.tabs(["📊 總覽儀表板", "📅 年度戰績回顧"])

if st.button("🔄 重新整理數據"):
    st.cache_resource.clear()
    st.rerun()

xls, err_msg = load_google_sheet()

if err_msg:
    st.error("無法連線到 Google Sheet")
else:
    with tab1:
        if '累積總表' in xls.sheet_names:
            try:
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
                        st.plotly_chart(px.line(df_total, y=y_col, title="歷史資金成長"), use_container_width=True)
            except: pass

    with tab2:
        target_years = [2025, 2024, 2023, 2022, 2021]
        my_bar = st.progress(0, text="下載中...")
        for i, year in enumerate(target_years):
            result = plot_yearly_trend(xls, year)
            if result:
                fig, final, high, low, m_stats = result
                
                # 這裡保留頁面標題，但圖表標題已移除
                st.markdown(f"### {year} 年" + (" (記錄較不完整)" if year in [2021, 2022] else ""))
                
                c1, c2, c3 = st.columns(3)
                c1.metric("總損益", f"${final:,.0f}") 
                c2.metric("高點", f"${high:,.0f}")
                c3.metric("低點", f"${low:,.0f}")
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.caption(f"📅 {year} 各月損益：")
                st.dataframe(pd.DataFrame([m_stats]), hide_index=True, use_container_width=True)
                st.markdown("---")
            my_bar.progress((i + 1) / len(target_years))
        my_bar.empty()
