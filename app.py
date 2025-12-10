import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室 (雲端同步版)")

# --- 2. 連線設定 (讀取 Secrets) ---
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

# --- 3. 資料讀取輔助函式 ---
def read_daily_pnl(xls, sheet_name):
    try:
        # 讀前 15 行找標題
        df_preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
        header_idx = -1
        target_keywords = ['日總計', '累計損益', '損益']
        
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
                if '損益' in str(col) and '累計' not in str(col): pnl_col = col; break
        
        if 'Date' in df.columns and pnl_col:
            df = df[['Date', pnl_col]].copy()
            df = df.rename(columns={pnl_col: 'Daily_PnL'})
            
            # 清洗數據
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Daily_PnL'] = pd.to_numeric(df['Daily_PnL'], errors='coerce')
            df = df.dropna(subset=['Date', 'Daily_PnL'])
            return df
            
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 4. 繪圖邏輯 (新增月統計功能) ---
def plot_yearly_trend(xls, year):
    all_data = []
    # 掃描分頁
    for month in range(1, 13): 
        sheet_name = f"日報表{year}-{month:02d}"
        if sheet_name in xls.sheet_names:
            df_m = read_daily_pnl(xls, sheet_name)
            if not df_m.empty: all_data.append(df_m)
    
    if not all_data: return None 

    # 合併數據
    df_year = pd.concat(all_data)
    
    # 年份過濾 (修正 2023 重複問題)
    df_year = df_year[df_year['Date'].dt.year == year]
    
    if df_year.empty: return None

    df_year = df_year.sort_values('Date')
    df_year['Cumulative_PnL'] = df_year['Daily_PnL'].cumsum()
    
    # 準備圖表數據
    latest_pnl = df_year['Cumulative_PnL'].iloc[-1]
    max_pnl = df_year['Cumulative_PnL'].max()
    min_pnl = df_year['Cumulative_PnL'].min()
    
    # --- 新增：計算每月總損益 ---
    # 使用 groupby 依照月份加總 Daily_PnL
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    
    # 建立顯示用的字典 (1月~12月)
    monthly_stats_display = {}
    for m in range(1, 13):
        col_name = f"{m}月"
        if m in monthly_sums.index:
            val = monthly_sums[m]
            # 格式化金額：正數亮紅，負數亮綠 (或只顯示金額) -> 這裡先純顯示金額比較整齊
            monthly_stats_display[col_name] = f"${val:,.0f}"
        else:
            monthly_stats_display[col_name] = "---" # 未來月份顯示橫線

    # 繪圖
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_year['Date'], y=df_year['Cumulative_PnL'],
        mode='lines', name=f'{year}損益',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'
    ))
    
    # 畫月份線
    df_year['Month'] = df_year['Date'].dt.month
    month_starts = df_year.groupby('Month')['Date'].min()
    for m_idx, start_date in month_starts.items():
        if m_idx == 1: continue
        fig.add_vline(x=start_date, line_width=1, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title=f"<b>{year} 年度損益走勢</b> (總獲利: ${latest_pnl:,.0f})",
        xaxis_title="日期", yaxis_title="累計損益",
        hovermode="x unified", height=500, xaxis=dict(dtick="M1", tickformat="%b") 
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
                # 簡單抓取累積總表
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

    # === Tab 2: 年度回顧 (含月損益表) ===
    with tab2:
        target_years = [2025, 2024, 2023, 2022, 2021]
        
        my_bar = st.progress(0, text="正在下載雲端資料...")
        
        for i, year in enumerate(target_years):
            result = plot_yearly_trend(xls, year)
            if result:
                fig, final, high, low, m_stats = result # 多接收一個 m_stats
                
                st.markdown(f"### {year} 年")
                
                # 1. 顯示年度 KPI
                k1, k2, k3 = st.columns(3)
                k1.metric(f"{year} 總損益", f"${final:,.0f}")
                k2.metric("高點", f"${high:,.0f}")
                k3.metric("低點", f"${low:,.0f}")
                
                # 2. 顯示圖表
                st.plotly_chart(fig, use_container_width=True)
                
                # 3. 顯示每月損益表 (New!)
                st.caption(f"📅 {year} 各月損益統計：")
                # 轉成 DataFrame 顯示比較整齊
                df_m_stats = pd.DataFrame([m_stats])
                st.dataframe(df_m_stats, hide_index=True, use_container_width=True)
                
                st.markdown("---")
            
            my_bar.progress((i + 1) / len(target_years))
        
        my_bar.empty()
