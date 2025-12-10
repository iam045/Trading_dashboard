import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# --- 1. 頁面設定 ---
st.set_page_config(page_title="私募基金戰情室 (診斷模式)", layout="wide")
st.title("🚑 資料診斷模式：為什麼 9 月讀不到？")

# --- 2. 連線設定 ---
@st.cache_resource(ttl=0) # 設定 0 秒快取，強制每次都重新下載
def load_google_sheet():
    try:
        if "google_sheet_id" not in st.secrets:
            return None, "請設定 Secrets"
        sheet_id = st.secrets["google_sheet_id"]
        # 加一個隨機參數，試圖騙過 Google 快取
        import time
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&t={int(time.time())}"
        return pd.ExcelFile(url, engine='openpyxl'), None
    except Exception as e:
        return None, f"連線錯誤: {e}"

xls, err_msg = load_google_sheet()

if err_msg:
    st.error(err_msg)
    st.stop()

# ==========================================
# 🛑 診斷區域：直接把 9 月的內臟挖出來看
# ==========================================
with st.container():
    st.error("👇 【診斷報告】請看這裡 👇")
    
    # 1. 檢查分頁是否存在
    all_sheets = xls.sheet_names
    st.write(f"1. Python 讀到的所有分頁清單 (共 {len(all_sheets)} 頁):")
    st.code(str(all_sheets))
    
    # 2. 鎖定 9 月分頁
    target_9 = None
    for name in all_sheets:
        if "2025" in name and ("09" in name or "-9" in name):
            target_9 = name
            break
            
    if target_9:
        st.success(f"✅ 找到了 9 月分頁，名稱為：[{target_9}]")
        
        # 3. 讀取原始資料 (前 20 行)
        st.write("3. 讀取該分頁的前 20 行原始資料 (Header=None):")
        df_raw = pd.read_excel(xls, sheet_name=target_9, header=None, nrows=20)
        st.dataframe(df_raw)
        
        # 4. 尋找關鍵字位置
        row_idx = -1
        col_idx = -1
        for r_idx, row in enumerate(df_raw.values):
            row_str = "".join([str(v) for v in row])
            if "日總計" in row_str:
                row_idx = r_idx
                st.info(f"👉 在第 {r_idx} 列 (Row) 發現 '日總計' 關鍵字！")
                break
        
        if row_idx != -1:
            # 5. 嘗試正規讀取
            df_clean = pd.read_excel(xls, sheet_name=target_9, header=row_idx)
            st.write(f"4. 以第 {row_idx} 列為標題讀取後，欄位名稱為：")
            st.write(list(df_clean.columns))
            
            # 尋找損益欄位
            pnl_col = None
            for c in df_clean.columns:
                if "日總計" in str(c).replace(" ",""): pnl_col = c
            
            if pnl_col:
                st.write(f"✅ 鎖定損益欄位: [{pnl_col}]")
                st.write("5. 檢查該欄位數據 (前 10 筆):")
                st.dataframe(df_clean[['Date', pnl_col]].head(10))
                
                # 測試轉型
                try:
                    df_clean[pnl_col] = pd.to_numeric(df_clean[pnl_col].astype(str).str.replace(',', ''), errors='coerce')
                    valid_count = df_clean[pnl_col].count()
                    st.write(f"📊 轉成數字後，有效的資料筆數: {valid_count} 筆")
                    if valid_count == 0:
                        st.error("❌ 嚴重警告：轉成數字後剩下 0 筆！代表 Excel 裡的數字格式有問題 (可能是文字格式)。")
                except Exception as e:
                    st.error(f"❌ 轉型失敗: {e}")
            else:
                st.error("❌ 雖然找到標題列，但找不到 '日總計' 欄位。")
        else:
            st.error("❌ 在前 20 行完全找不到 '日總計' 三個字！(可能標題在更下面？)")
            
    else:
        st.error("❌ 在 Excel 裡完全找不到 2025 年 9 月的分頁！(請檢查 Google 快取是否未更新)")

st.markdown("---")

# ==========================================
# 下面是原本的正常程式碼 (保持不變)
# ==========================================

# ... (以下為原本的 read_daily_pnl, plot_yearly_trend 等函式，為了版面我不重複貼，請保留原本的邏輯) ...
# 為了讓你直接能跑，我把必要的函式補在下面，你可以直接複製整段

def read_daily_pnl(xls, sheet_name):
    try:
        df_preview = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=30)
        header_idx = -1
        target_keywords = ['日總計', '總計', '累計損益', '損益']
        for i, row in enumerate(df_preview.values):
            row_str = "".join([str(r) for r in row])
            if any(k in row_str for k in target_keywords):
                header_idx = i
                break
        if header_idx == -1: return pd.DataFrame()

        df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx)
        new_cols = list(df.columns)
        new_cols[0] = 'Date'
        df.columns = new_cols
        
        pnl_col = None
        clean_cols = {str(c).replace(" ", ""): c for c in df.columns}
        if '日總計' in clean_cols: pnl_col = clean_cols['日總計']
        elif '總計' in clean_cols: pnl_col = clean_cols['總計']
        elif '累計損益' in clean_cols: pnl_col = clean_cols['累計損益']
        elif '損益' in clean_cols: pnl_col = clean_cols['損益']

        if 'Date' in df.columns and pnl_col:
            df = df[['Date', pnl_col]].copy()
            df = df.rename(columns={pnl_col: 'Daily_PnL'})
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Daily_PnL'] = pd.to_numeric(df['Daily_PnL'].astype(str).str.replace(',', ''), errors='coerce')
            df = df.dropna(subset=['Date', 'Daily_PnL'])
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def plot_yearly_trend(xls, year):
    all_data = []
    sheet_map = {re.sub(r"[ _－/.]", "-", str(name)): name for name in xls.sheet_names}
    for month in range(1, 13): 
        target_names = [f"日報表{year}-{month:02d}", f"日報表{year}-{month}"]
        real_sheet_name = None
        for t in target_names:
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
    
    monthly_sums = df_year.groupby(df_year['Date'].dt.month)['Daily_PnL'].sum()
    monthly_stats_display = {}
    for m in range(1, 13):
        monthly_stats_display[f"{m}月"] = f"${monthly_sums[m]:,.0f}" if m in monthly_sums.index else "---"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_year['Date'], y=df_year['Cumulative_PnL'],
        mode='lines', name=f'{year}損益',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'
    ))
    df_year['Month'] = df_year['Date'].dt.month
    month_starts = df_year.groupby('Month')['Date'].min()
    tick_vals = []; tick_text = []
    for m_idx, start_date in month_starts.items():
        tick_vals.append(start_date); tick_text.append(f"{m_idx}月")
        if m_idx == 1: continue
        fig.add_vline(x=start_date, line_width=1, line_dash="dash", line_color="gray", opacity=0.3)

    title_suffix = " <span style='color:red; font-size: 0.8em;'>(記錄較不完整)</span>" if year in [2021, 2022] else ""
    fig.update_layout(
        title=f"<b>{year} 年度損益走勢</b>{title_suffix} (總獲利: ${latest_pnl:,.0f})",
        margin=dict(t=40, b=10), xaxis_title="", yaxis_title="累計損益",
        hovermode="x unified", height=450, showlegend=False,
        xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_text)
    )
    return fig, latest_pnl, max_pnl, min_pnl, monthly_stats_display

# --- 主程式 ---
tab1, tab2 = st.tabs(["📊 總覽儀表板", "📅 年度戰績回顧"])

if st.button("🔄 重新整理數據"):
    st.cache_resource.clear()
    st.rerun()

# 總覽 Tab (簡化)
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

# 年度回顧 Tab
with tab2:
    target_years = [2025, 2024, 2023, 2022, 2021]
    for year in target_years:
        result = plot_yearly_trend(xls, year)
        if result:
            fig, final, high, low, m_stats = result
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"📅 {year} 各月損益：")
            st.dataframe(pd.DataFrame([m_stats]), hide_index=True, use_container_width=True)
            st.markdown("---")
