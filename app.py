import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import time

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
        # 加 timestamp 避免快取
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"
        return pd.ExcelFile(url, engine='openpyxl'), None
    except Exception as e:
        return None, f"無法讀取雲端檔案: {e}"

# --- 3. 資料讀取 (三階段篩選版) ---
def read_daily_pnl(xls, sheet_name):
    try:
        # 先把整張表讀進來 (不設標題)
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=50)
        
        header_row = -1
        pnl_col_idx = -1
        found_mode = ""

        # === 第一階段：優先尋找 '日總計' ===
        for r in range(len(df_raw)):
            row_values = [str(v).replace(" ", "") for v in df_raw.iloc[r]]
            if "日總計" in row_values:
                header_row = r
                # 找出 '日總計' 在哪一欄
                for c, val in enumerate(row_values):
                    if "日總計" in val:
                        pnl_col_idx = c
                        found_mode = "日總計"
                        break
                break
        
        # === 第二階段：如果沒找到，尋找 '總計' (排除 '累計') ===
        if header_row == -1:
            for r in range(len(df_raw)):
                row_values = [str(v).replace(" ", "") for v in df_raw.iloc[r]]
                # 檢查這一行有沒有單純的 '總計'
                for c, val in enumerate(row_values):
                    if "總計" in val and "累計" not in val and "日" not in val:
                        header_row = r
                        pnl_col_idx = c
                        found_mode = "總計"
                        break
                if header_row != -1: break

        # === 提取資料 ===
        if header_row != -1 and pnl_col_idx != -1:
            # 依照找到的標題位置讀取
            df = df_raw.iloc[header_row+1:, [0, pnl_col_idx]].copy()
            df.columns = ['Date', 'Daily_PnL']
            
            # 清洗並驗證
            df_clean = clean_data(df)
            if not df_clean.empty:
                return df_clean

        # === 第三階段：暴力指定 H7 (H欄=Index 7, 第7列=Index 6) ===
        # 如果上面都失敗，或讀出來沒資料，直接抓固定位置
        if df_raw.shape[0] > 6 and df_raw.shape[1] > 7:
            df_force = df_raw.iloc[6:, [0, 7]].copy()
            df_force.columns = ['Date', 'Daily_PnL']
            return clean_data(df_force)

        return pd.DataFrame()

    except: return pd.DataFrame()

def clean_data(df):
    """共用的資料清洗函式"""
    # 轉日期
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    # 轉數字 (去逗號、去空格)
    df['Daily_PnL'] = pd.to_numeric(df['Daily_PnL'].astype(str).str.replace(',', '').str.strip(), errors='coerce')
    # 移除無效列
    return df.dropna(subset=['Date', 'Daily_PnL'])

# --- 4. 繪圖邏輯 ---
def plot_yearly_trend(xls, year):
    all_data = []
    
    # 分頁名稱清洗
    sheet_map = {re.sub(r"[ _－/.-]", "", str(name)): name for name in xls.sheet_names}
    
    for month in range(1, 13): 
        # 嘗試名稱
        targets = [f"日報表{year}{month:02d}", f"日報表{year}{month}"]
        
        real_sheet_name = None
        for t in targets:
            if t in sheet_map:
                real_sheet_name = sheet_map[t]
                break
            
        if real_sheet_name:
            df_m = read_daily_pnl(xls, real_sheet_name)
            if not df_m.empty: all_data.append(df_m)
    
    if not all_data: return None 

    df_year = pd.concat(all_data)
    df_year = df_year[df_year['Date'].dt.year == year]
    
    if df_year.empty: return None

    df_year = df_year.sort_values('Date')
    df_year['Cumulative_PnL'] = df_year['Daily_PnL'].cumsum()
    
    latest_pnl = df_year['Cumulative_PnL'].iloc[-1]
    max_pnl = df_year['Cumulative_PnL'].max()
    min_pnl = df_year['Cumulative_PnL'].min()
    
    # 月統計
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    monthly_stats_display = {}
    for m in range(1, 13):
        val = monthly_sums.get(m, None)
        monthly_stats_display[f"{m}月"] = f"${val:,.0f}" if val is not None else "---"

    # 繪圖
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_year['Date'], y=df_year['Cumulative_PnL'],
        mode='lines',
        name=f'{year}損益',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy', 
        fillcolor='rgba(31, 119, 180, 0.1)'
    ))

    df_year['Month'] = df_year['Date'].dt.month
    month_starts = df_year.groupby('Month')['Date'].min()
    
    tick_vals = []
    tick_text = []
    for m_idx, start_date in month_starts.items():
        tick_vals.append(start_date)
        tick_text.append(f"{m_idx}月")
        if m_idx == 1: continue
        fig.add_vline(x=start_date, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    fig.update_layout(
        # 這裡已經移除了 title 參數，達成你的要求
        margin=dict(t=20, b=10), # 上邊距留一點空間給年份標題(因為圖表標題拿掉了)
        xaxis_title="", 
        yaxis_title="累計損益",
        hovermode="x unified", 
        height=450,
        showlegend=False,
        xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_text)
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
    # Tab 1
    with tab1:
        if '累積總表' in xls.sheet_names:
            try:
                df_preview = pd.read_excel(xls, '累積總表', header=None, nrows=10)
                h_idx = 0
                for i, row in enumerate(df_preview.values):
                    if '累積損益' in "".join([str(r) for r in row]): h_idx = i; break
                
                df_total = pd.read_excel(xls, '累積總表', header=h_idx)
                
                y_col = None
                for col in df_total.columns:
                    if '累積損益' in str(col): y_col = col; break
                
                if y_col:
                    latest_val = df_total[y_col].iloc[-1]
                    st.metric("歷史總權益", f"${latest_val:,.0f}")
                    fig = px.line(df_total, y=y_col, title="歷史資金成長")
                    st.plotly_chart(fig, use_container_width=True)
            except: pass

    # Tab 2
    with tab2:
        target_years = [2025, 2024, 2023, 2022, 2021]
        my_bar = st.progress(0, text="下載中...")
        for i, year in enumerate(target_years):
            result = plot_yearly_trend(xls, year)
            if result:
                fig, final, high, low, m_stats = result
                
                # 標題 (整合備註)
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
