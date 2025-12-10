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
        # 加 timestamp 避免快取舊檔
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"
        return pd.ExcelFile(url, engine='openpyxl'), None
    except Exception as e:
        return None, f"無法讀取雲端檔案: {e}"

# --- 3. 資料讀取 (包含 H7 暴力指定法) ---
def read_daily_pnl(xls, sheet_name):
    try:
        # === 方法 A: 原本的關鍵字搜尋 (針對舊年份) ===
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=30)
        target_keywords = ['日總計', '總計', '累計損益', '損益']
        
        header_row = -1
        pnl_col = -1
        
        for r in range(len(df_raw)):
            for c in range(len(df_raw.columns)):
                val = str(df_raw.iloc[r, c]).replace(" ", "")
                if any(k in val for k in target_keywords):
                    header_row = r
                    pnl_col = c
                    break
            if header_row != -1: break
            
        if header_row != -1:
            # 找到關鍵字，正常讀取
            df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)
            # 強制指定欄位
            df_data = df.iloc[:, [0, pnl_col]].copy()
            df_data.columns = ['Date', 'Daily_PnL']
        
        else:
            # === 方法 B: 指定座標暴力讀取 (針對 2025-09 這種抓不到的) ===
            # 你說資料在 H7:H28 (H是第8個字母，Index=7)
            # 假設日期在 A 欄 (Index=0)
            # skiprows=6 代表跳過前6行，從 Excel 第7行開始讀
            
            # 嘗試讀取 A欄(0) 和 H欄(7)
            try:
                df_force = pd.read_excel(xls, sheet_name=sheet_name, header=None, skiprows=6, usecols=[0, 7])
                if not df_force.empty:
                    df_force.columns = ['Date', 'Daily_PnL']
                    df_data = df_force
                else:
                    return pd.DataFrame()
            except:
                return pd.DataFrame()

        # --- 共同清洗邏輯 ---
        df_data['Date'] = pd.to_datetime(df_data['Date'], errors='coerce')
        df_data['Daily_PnL'] = pd.to_numeric(df_data['Daily_PnL'].astype(str).str.replace(',', ''), errors='coerce')
        df_data = df_data.dropna(subset=['Date', 'Daily_PnL'])
        
        return df_data
            
    except: return pd.DataFrame()

# --- 4. 繪圖邏輯 ---
def plot_yearly_trend(xls, year):
    all_data = []
    
    # 分頁名稱清洗 (移除所有符號)
    sheet_map = {re.sub(r"[ _－/.-]", "", str(name)): name for name in xls.sheet_names}
    
    for month in range(1, 13): 
        # 嘗試名稱: 202509, 20259
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

    title_suffix = " <span style='color:red; font-size: 0.8em;'>(記錄較不完整)</span>" if year in [2021, 2022] else ""

    fig.update_layout(
        title=f"<b>{year} 年度損益走勢</b>{title_suffix} (總獲利: ${latest_pnl:,.0f})",
        margin=dict(t=40, b=10),
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
                
                title_extra = " (記錄較不完整)" if year in [2021, 2022] else ""
                st.markdown(f"### {year} 年{title_extra}")
                
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
