import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室 (雲端同步版 - Pro Ver 5.6)")

# --- 2. 連線設定 ---
@st.cache_resource(ttl=60) 
def load_google_sheet():
    try:
        if "google_sheet_id" not in st.secrets:
            return None, "請在 Streamlit Secrets 設定 'google_sheet_id'"
            
        sheet_id = st.secrets["google_sheet_id"]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        
        xls = pd.ExcelFile(url, engine='openpyxl')
        return xls, None
    except Exception as e:
        return None, f"無法讀取雲端檔案。錯誤訊息：{e}"

# --- 3. 資料讀取 (增強搜尋版) ---
def read_daily_pnl(xls, sheet_name):
    try:
        # 擴大搜尋範圍到前 30 行 (以免標題太下面)
        df_preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=30)
        header_idx = -1
        target_keywords = ['日總計', '總計', '累計損益', '損益']
        
        for i, row in enumerate(df_preview.values):
            if any(k in str(r) for k in target_keywords for r in row):
                header_idx = i
                break
        
        if header_idx == -1: return pd.DataFrame()

        df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx)
        
        # 強制命名第一欄為 Date
        new_cols = list(df.columns)
        new_cols[0] = 'Date'
        df.columns = new_cols
        
        # 尋找損益欄位
        pnl_col = None
        for col in df.columns:
            if '日總計' in str(col): pnl_col = col; break
        if not pnl_col:
            for col in df.columns:
                if '總計' in str(col) and '累計' not in str(col): pnl_col = col; break
        if not pnl_col:
            for col in df.columns:
                if '損益' in str(col) and '累計' not in str(col): pnl_col = col; break
        
        if 'Date' in df.columns and pnl_col:
            df = df[['Date', pnl_col]].copy()
            df = df.rename(columns={pnl_col: 'Daily_PnL'})
            
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Daily_PnL'] = pd.to_numeric(df['Daily_PnL'], errors='coerce')
            df = df.dropna(subset=['Date', 'Daily_PnL'])
            return df
            
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 4. 繪圖邏輯 (還原藍線 + 強力搜尋分頁) ---
def plot_yearly_trend(xls, year):
    all_data = []
    
    # 建立分頁名稱對照表 (把所有分頁名稱的空白拿掉，做成乾淨的對照表)
    # 格式: {'日報表2025-09': '日 報 表 2025 - 09', ...}
    clean_sheet_map = {name.replace(" ", ""): name for name in xls.sheet_names}
    
    for month in range(1, 13): 
        # 我們要找的目標名稱 (無空白標準版)
        target_v1 = f"日報表{year}-{month:02d}" # 09
        target_v2 = f"日報表{year}-{month}"     # 9
        
        real_sheet_name = None
        if target_v1 in clean_sheet_map:
            real_sheet_name = clean_sheet_map[target_v1]
        elif target_v2 in clean_sheet_map:
            real_sheet_name = clean_sheet_map[target_v2]
            
        if real_sheet_name:
            df_m = read_daily_pnl(xls, real_sheet_name)
            if not df_m.empty: all_data.append(df_m)
    
    if not all_data: return None 

    # 合併數據
    df_year = pd.concat(all_data)
    df_year = df_year[df_year['Date'].dt.year == year]
    
    if df_year.empty: return None

    df_year = df_year.sort_values('Date')
    df_year['Cumulative_PnL'] = df_year['Daily_PnL'].cumsum()
    
    latest_pnl = df_year['Cumulative_PnL'].iloc[-1]
    max_pnl = df_year['Cumulative_PnL'].max()
    min_pnl = df_year['Cumulative_PnL'].min()
    
    # 計算月損益
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    monthly_stats_display = {}
    for m in range(1, 13):
        col_name = f"{m}月"
        if m in monthly_sums.index:
            monthly_stats_display[col_name] = f"${monthly_sums[m]:,.0f}"
        else:
            monthly_stats_display[col_name] = "---"

    # --- 繪圖 (回歸經典藍色) ---
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_year['Date'], y=df_year['Cumulative_PnL'],
        mode='lines',
        name=f'{year}損益',
        line=dict(color='#1f77b4', width=2), # 經典藍
        fill='tozeroy', 
        fillcolor='rgba(31, 119, 180, 0.1)' # 淡淡的藍色背景
    ))

    # 畫月份分隔線
    df_year['Month'] = df_year['Date'].dt.month
    month_starts = df_year.groupby('Month')['Date'].min()
    
    # 準備 X 軸刻度 (中文月份)
    tick_vals = []
    tick_text = []
    
    for m_idx, start_date in month_starts.items():
        tick_vals.append(start_date)
        tick_text.append(f"{m_idx}月")
        
        if m_idx == 1: continue
        fig.add_vline(x=start_date, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    # 處理標題後綴
    title_suffix = ""
    if year in [2021, 2022]:
        title_suffix = " <span style='color:red; font-size: 0.8em;'>(記錄較不完整)</span>"

    fig.update_layout(
        title=f"<b>{year} 年度損益走勢</b>{title_suffix} (總獲利: ${latest_pnl:,.0f})",
        xaxis_title="", 
        yaxis_title="累計損益",
        hovermode="x unified", 
        height=500,
        showlegend=False,
        xaxis=dict(
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_text
        )
    )
    
    return fig, latest_pnl, max_pnl, min_pnl, monthly_stats_display

# --- 5. 執行主程式 ---
tab1, tab2 = st.tabs(["📊 總覽儀表板", "📅 年度戰績回顧"])

if st.button("🔄 重新整理數據"):
    st.cache_resource.clear()
    st.rerun()

xls, err_msg = load_google_sheet()

if err_msg:
    st.error("無法連線到 Google Sheet！請檢查 Secrets 設定是否正確。")
else:
    # === Tab 1: 總覽 ===
    with tab1:
        if '累積總表' in xls.sheet_names:
            try:
                df_preview = pd.read_excel(xls, '累積總表', header=None, nrows=5)
                h_idx = 0
                for i, row in enumerate(df_preview.values):
                    if '累積損益' in str(row): h_idx = i; break
                
                df_total = pd.read_excel(xls, '累積總表', header=h_idx)
                
                y_col = None
                for col in df_total.columns:
                    if '累積損益' in str(col): y_col = col; break
                
                if y_col:
                    latest_val = df_total[y_col].iloc[-1]
                    st.metric("歷史總權益", f"${latest_val:,.0f}")
                    fig = px.line(df_total, y=y_col, title="歷史資金成長")
                    st.plotly_chart(fig, use_container_width=True)
            except:
                st.warning("累積總表格式讀取異常。")

    # === Tab 2: 年度回顧 ===
    with tab2:
        target_years = [2025, 2024, 2023, 2022, 2021]
        
        my_bar = st.progress(0, text="正在下載雲端資料...")
        
        for i, year in enumerate(target_years):
            result = plot_yearly_trend(xls, year)
            if result:
                fig, final, high, low, m_stats = result
                
                # 判斷是否加備註文字
                title_extra = " (記錄較不完整)" if year in [2021, 2022] else ""
                st.markdown(f"### {year} 年{title_extra}")
                
                k1, k2, k3 = st.columns(3)
                k1.metric(f"{year} 總損益", f"${final:,.0f}", delta_color="off") 
                k2.metric("高點", f"${high:,.0f}")
                k3.metric("低點", f"${low:,.0f}")
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.caption(f"📅 {year} 各月損益統計：")
                df_m_stats = pd.DataFrame([m_stats])
                st.dataframe(df_m_stats, hide_index=True, use_container_width=True)
                
                st.markdown("---")
            
            my_bar.progress((i + 1) / len(target_years))
        
        my_bar.empty()
