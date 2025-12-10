import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np # 新增 numpy 用於數學運算

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室 (雲端同步版 - Pro Ver 5.5)")

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

# --- 3. 資料讀取 (相容性增強版) ---
def read_daily_pnl(xls, sheet_name):
    try:
        # 讀前 15 行找標題
        df_preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
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

# --- 4. 繪圖邏輯 (紅綠分色 + 月份修正) ---
def plot_yearly_trend(xls, year):
    all_data = []
    
    # 修正：同時搜尋 "09" 和 "9" 兩種格式
    for month in range(1, 13): 
        # 嘗試格式 1: 日報表2025-09
        name_v1 = f"日報表{year}-{month:02d}"
        # 嘗試格式 2: 日報表2025-9
        name_v2 = f"日報表{year}-{month}"
        
        sheet_name = None
        if name_v1 in xls.sheet_names:
            sheet_name = name_v1
        elif name_v2 in xls.sheet_names:
            sheet_name = name_v2
            
        if sheet_name:
            df_m = read_daily_pnl(xls, sheet_name)
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
    
    # 計算月損益 (表格用)
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    monthly_stats_display = {}
    for m in range(1, 13):
        col_name = f"{m}月"
        if m in monthly_sums.index:
            monthly_stats_display[col_name] = f"${monthly_sums[m]:,.0f}"
        else:
            monthly_stats_display[col_name] = "---"

    # --- 🔥 紅綠分色繪圖邏輯 ---
    fig = go.Figure()

    # 我們需要畫兩條線：
    # 1. 正數線 (只顯示 >0 的部分，<0 補 0) -> 紅色
    # 2. 負數線 (只顯示 <0 的部分，>0 補 0) -> 綠色
    # 注意：這樣做在交界處會有一點點斷層，但在日報表這種密度下通常看不出來，或是用 fill 覆蓋
    
    # 為了讓線條連續，我們畫一條主線(透明)，然後用 fill 來上色
    # 更好的做法：分段填色
    
    # 準備數據
    x_data = df_year['Date']
    y_data = df_year['Cumulative_PnL']
    
    # 製作 "正數區域" (小於 0 的變 0)
    y_positive = y_data.clip(lower=0)
    # 製作 "負數區域" (大於 0 的變 0)
    y_negative = y_data.clip(upper=0)
    
    # 1. 畫紅色區域 (0軸以上)
    fig.add_trace(go.Scatter(
        x=x_data, y=y_positive,
        mode='lines',
        name='獲利',
        line=dict(color='#ff4d4d', width=2), # 紅色線
        fill='tozeroy', 
        fillcolor='rgba(255, 77, 77, 0.1)' # 紅色半透明填充
    ))
    
    # 2. 畫綠色區域 (0軸以下)
    fig.add_trace(go.Scatter(
        x=x_data, y=y_negative,
        mode='lines',
        name='虧損',
        line=dict(color='#00cc66', width=2), # 綠色線
        fill='tozeroy', 
        fillcolor='rgba(0, 204, 102, 0.1)' # 綠色半透明填充
    ))

    # 畫月份分隔線
    df_year['Month'] = df_year['Date'].dt.month
    month_starts = df_year.groupby('Month')['Date'].min()
    
    # 收集 X 軸刻度 (用於顯示中文月份)
    tick_vals = []
    tick_text = []
    
    for m_idx, start_date in month_starts.items():
        tick_vals.append(start_date)
        tick_text.append(f"{m_idx}月") # 轉成中文
        
        if m_idx == 1: continue
        fig.add_vline(x=start_date, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    fig.update_layout(
        title=f"<b>{year} 年度損益走勢</b> (總獲利: ${latest_pnl:,.0f})",
        xaxis_title="", 
        yaxis_title="累計損益",
        hovermode="x unified", 
        height=500,
        showlegend=False, # 隱藏圖例讓畫面乾淨
        # 自訂 X 軸刻度顯示
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
                
                st.markdown(f"### {year} 年")
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
