import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室", layout="wide")
st.title("💰 交易績效戰情室 (雲端同步版 - Pro Ver 5.8 終極偵錯)")

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

# --- 3. 資料讀取 (暴力搜尋版) ---
def read_daily_pnl(xls, sheet_name):
    try:
        # 1. 擴大搜尋範圍到前 50 行
        # header=None 代表先不設標題，把整張表當資料讀進來
        df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=50)
        
        header_idx = -1
        # 關鍵字增加空白變體
        target_keywords = ['日總計', '總計', '累計損益', '損益', '日 總 計', '損 益']
        
        # 逐行掃描
        for i, row in enumerate(df_raw.values):
            row_str = " ".join([str(r) for r in row]) # 把整行轉成字串
            if any(k in row_str for k in target_keywords):
                header_idx = i
                break
        
        # 除錯：如果是在找 9 月份的表，印出它到底在第幾行找到標題
        # if "09" in sheet_name or "-9" in sheet_name:
        #     print(f"[{sheet_name}] 標題在第 {header_idx} 行")

        if header_idx == -1: return pd.DataFrame()

        # 2. 用找到的行數當標題重新讀取
        df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx)
        
        # 3. 欄位清洗 (把換行符號、前後空白都拿掉)
        df.columns = df.columns.astype(str).str.replace('\n', '').str.strip()
        
        # 強制命名第一欄為 Date (假設第一欄永遠是日期)
        new_cols = list(df.columns)
        new_cols[0] = 'Date'
        df.columns = new_cols
        
        # 4. 尋找損益欄位 (模糊比對)
        pnl_col = None
        for col in df.columns:
            if '日總計' in col.replace(" ", ""): pnl_col = col; break # 移除空白比對
        if not pnl_col:
            for col in df.columns:
                if '總計' in col and '累計' not in col: pnl_col = col; break
        if not pnl_col:
            for col in df.columns:
                if '損益' in col and '累計' not in col: pnl_col = col; break
        
        if 'Date' in df.columns and pnl_col:
            df = df[['Date', pnl_col]].copy()
            df = df.rename(columns={pnl_col: 'Daily_PnL'})
            
            # 清洗數據
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            # 處理千分位逗號和非數字字符
            df['Daily_PnL'] = pd.to_numeric(df['Daily_PnL'].astype(str).str.replace(',', ''), errors='coerce')
            
            df = df.dropna(subset=['Date', 'Daily_PnL'])
            return df
            
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 4. 繪圖邏輯 ---
def plot_yearly_trend(xls, year):
    all_data = []
    
    # 清洗分頁名稱對照表
    sheet_map = {re.sub(r"[ _－/.]", "-", str(name)): name for name in xls.sheet_names}
    
    for month in range(1, 13): 
        target_v1 = f"日報表{year}-{month:02d}" 
        target_v2 = f"日報表{year}-{month}"     
        
        real_sheet_name = None
        if target_v1 in sheet_map: real_sheet_name = sheet_map[target_v1]
        elif target_v2 in sheet_map: real_sheet_name = sheet_map[target_v2]
            
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
    
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    monthly_stats_display = {}
    for m in range(1, 13):
        col_name = f"{m}月"
        if m in monthly_sums.index:
            monthly_stats_display[col_name] = f"${monthly_sums[m]:,.0f}"
        else:
            monthly_stats_display[col_name] = "---"

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
        margin=dict(t=10),
        xaxis_title="", 
        yaxis_title="累計損益",
        hovermode="x unified", 
        height=450,
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
        # --- 診斷區域：針對 2025 年 9 月 (隱藏式) ---
        with st.expander("🕵️‍♂️ 9月資料失蹤偵探 (Debug)"):
            st.write("正在檢查 Excel 裡的分頁名稱...")
            found_9 = False
            for name in xls.sheet_names:
                if "2025" in name and ("09" in name or "-9" in name):
                    st.write(f"✅ 找到分頁: **{name}**")
                    found_9 = True
                    # 嘗試讀取內容並顯示前 5 行
                    try:
                        df_debug = pd.read_excel(xls, sheet_name=name, header=None, nrows=10)
                        st.write("👇 該分頁的前 10 行內容 (請檢查 '日總計' 在哪)：")
                        st.dataframe(df_debug)
                    except:
                        st.write("❌ 讀取內容失敗")
            
            if not found_9:
                st.error("❌ 完全找不到包含 '2025' 和 '9' 的分頁名稱！")

        target_years = [2025, 2024, 2023, 2022, 2021]
        
        my_bar = st.progress(0, text="正在下載雲端資料...")
        
        for i, year in enumerate(target_years):
            result = plot_yearly_trend(xls, year)
            if result:
                fig, final, high, low, m_stats = result
                
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
