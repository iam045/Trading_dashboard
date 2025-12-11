import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
import time
import numpy as np
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室")

# --- 2. 連線與快取設定 ---
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

# --- 3. 資料處理核心邏輯 ---
def clean_numeric_column(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def read_daily_pnl(xls, sheet_name):
    try:
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=50)
        
        # [策略 A] 關鍵字搜尋
        target_keywords = ['日總計', '總計', '累計損益', '損益']
        header_row, pnl_col_idx = -1, -1
        
        for r in range(len(df_raw)):
            row_vals = [str(v).replace(" ", "") for v in df_raw.iloc[r]]
            if any(k in v for k in target_keywords for v in row_vals):
                header_row = r
                for c, val in enumerate(row_vals):
                    if any(k in val for k in target_keywords):
                        pnl_col_idx = c
                        break
                break
        
        if header_row != -1:
            df = df_raw.iloc[header_row+1:, [0, pnl_col_idx]].copy()
            df.columns = ['Date', 'Daily_PnL']
            df['Daily_PnL'] = clean_numeric_column(df['Daily_PnL'])
            if df['Daily_PnL'].count() > 0:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                return df.dropna(subset=['Date', 'Daily_PnL'])

        # [策略 B] 暴力指定 H7
        if df_raw.shape[0] > 6 and df_raw.shape[1] > 7:
            df_force = df_raw.iloc[6:, [0, 7]].copy()
            df_force.columns = ['Date', 'Daily_PnL']
            df_force['Date'] = pd.to_datetime(df_force['Date'], errors='coerce')
            df_force['Daily_PnL'] = clean_numeric_column(df_force['Daily_PnL'])
            return df_force.dropna(subset=['Date', 'Daily_PnL'])

        return pd.DataFrame()
    except: return pd.DataFrame()

def insert_zero_crossings(df):
    if df.empty: return df
    df = df.sort_values('Date').reset_index(drop=True)
    new_rows = []
    for i in range(len(df) - 1):
        curr, next_row = df.iloc[i], df.iloc[i+1]
        y1, y2 = curr['Cumulative_PnL'], next_row['Cumulative_PnL']
        if (y1 > 0 and y2 < 0) or (y1 < 0 and y2 > 0):
            t1, t2 = curr['Date'].timestamp(), next_row['Date'].timestamp()
            zero_t = t1 + (0 - y1) * (t2 - t1) / (y2 - y1)
            new_rows.append({
                'Date': pd.Timestamp.fromtimestamp(zero_t), 
                'Daily_PnL': 0, 'Cumulative_PnL': 0
            })
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        return df.sort_values('Date').reset_index(drop=True)
    return df

# --- 4. 繪圖核心 ---
def plot_yearly_trend(xls, year):
    sheet_map = {re.sub(r"[ _－/.-]", "", str(n)): n for n in xls.sheet_names}
    all_data = []

    for m in range(1, 13):
        targets = [f"日報表{year}{m:02d}", f"日報表{year}{m}"]
        real_name = next((sheet_map[t] for t in targets if t in sheet_map), None)
        if real_name:
            df_m = read_daily_pnl(xls, real_name)
            if not df_m.empty: all_data.append(df_m)
    
    if not all_data: return None

    df_year = pd.concat(all_data)
    df_year = df_year[df_year['Date'].dt.year == year]
    
    # --- 🔥 關鍵修正：如果是未來年 (2026)，不要過濾！ ---
    current_year = datetime.now().year
    if year == current_year:
        # 只有「今年」才需要砍掉未來的日期 (避免水平線)
        df_year = df_year[df_year['Date'] <= pd.Timestamp.now().normalize()]
    
    if df_year.empty: return None

    df_year = df_year.sort_values('Date')
    df_year['Cumulative_PnL'] = df_year['Daily_PnL'].cumsum()
    
    latest_pnl = df_year['Cumulative_PnL'].iloc[-1]
    max_pnl = df_year['Cumulative_PnL'].max()
    min_pnl = df_year['Cumulative_PnL'].min()
    
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    m_stats = {f"{m}月": f"${monthly_sums.get(m, 0):,.0f}" if m in monthly_sums else "---" for m in range(1, 13)}

    df_plot = insert_zero_crossings(df_year)
    y_pos = df_plot['Cumulative_PnL'].apply(lambda x: x if x >= 0 else None)
    y_neg = df_plot['Cumulative_PnL'].apply(lambda x: x if x <= 0 else None)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=y_pos, mode='lines', name='獲利',
                             line=dict(color='#ff4d4d', width=2), fill='tozeroy', fillcolor='rgba(255, 77, 77, 0.1)'))
    fig.add_trace(go.Scatter(x=df_plot['Date'], y=y_neg, mode='lines', name='虧損',
                             line=dict(color='#00cc66', width=2), fill='tozeroy', fillcolor='rgba(0, 204, 102, 0.1)'))

    month_starts = [pd.Timestamp(f"{year}-{m:02d}-01") for m in range(1, 13)]
    for d in month_starts:
        if d.month > 1: fig.add_vline(x=d, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis_title="", yaxis_title="累計損益",
        hovermode="x unified", height=450, showlegend=False,
        xaxis=dict(range=[f"{year}-01-01", f"{year}-12-31"], tickmode='array',
                   tickvals=month_starts, ticktext=[f"{m}月" for m in range(1, 13)])
    )
    return fig, latest_pnl, max_pnl, min_pnl, m_stats

# --- 5. 主程式執行 ---
tab1, tab2 = st.tabs(["📊 總覽儀表板", "📅 年度戰績回顧"])

if st.button("🔄 重新整理數據"):
    st.cache_resource.clear()
    st.rerun()

xls, err_msg = load_google_sheet()

if err_msg:
    st.error("無法連線到 Google Sheet，請檢查 Secrets 設定。")
else:
    # === Tab 1: 總覽 ===
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
                        import plotly.express as px
                        st.plotly_chart(px.line(df_total, y=y_col, title="歷史資金成長"), use_container_width=True)
            except: pass

    # === Tab 2: 年度回顧 (自動年份偵測) ===
    with tab2:
        detected_years = set()
        for name in xls.sheet_names:
            clean_name = re.sub(r"[ _－/.-]", "", str(name))
            match = re.search(r"日報表(\d{4})", clean_name)
            if match:
                detected_years.add(int(match.group(1)))
        
        target_years = sorted(list(detected_years), reverse=True) if detected_years else [2025, 2024, 2023, 2022, 2021]

        progress_bar = st.progress(0, text="數據載入中...")
        for i, year in enumerate(target_years):
            result = plot_yearly_trend(xls, year)
            if result:
                fig, final, high, low, m_stats = result
                note = " (記錄較不完整)" if year in [2021, 2022] else ""
                st.markdown(f"### {year} 年{note}")
                c1, c2, c3 = st.columns(3)
                c1.metric("總損益", f"${final:,.0f}") 
                c2.metric("高點", f"${high:,.0f}") 
                c3.metric("低點", f"${low:,.0f}")
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"📅 {year} 各月損益：")
                st.dataframe(pd.DataFrame([m_stats]), hide_index=True, use_container_width=True)
                st.markdown("---")
            progress_bar.progress((i + 1) / len(target_years))
        progress_bar.empty()

    # === 🔧 系統診斷室 (驗證用) ===
    with st.expander("🔧 系統診斷室 (點此檢查 Google 是否有傳回 2026)"):
        st.write("程式讀到的所有分頁清單：")
        st.code(xls.sheet_names)
        st.write(f"程式自動偵測到的年份：{target_years}")
