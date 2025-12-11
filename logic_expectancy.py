import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import calendar
import re

# ==========================================
# 1. 基礎運算與資料讀取 (Helper Functions)
# ==========================================

def clean_numeric(series):
    """清洗數字格式 (移除逗號、轉型)"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    """資料源 A: 讀取 '期望值' 分頁 (用於計算長期 KPI)"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        # 假設標題在第15列 -> header=14
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        if df.shape[1] < 14:
            return None, "期望值表格欄位不足 14 欄，請檢查格式。"

        # 欄位選取：日期(0), 策略(1), 最後總風險(10), 損益(11), R(13)
        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']

        df_clean['Date'] = df_clean['Date'].ffill() # 處理日期空白
        df_clean = df_clean.dropna(subset=['Strategy']) # 過濾小計行
        df_clean = df_clean.dropna(subset=['Date'])
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.normalize()
        
        for col in ['Risk_Amount', 'PnL', 'R']:
            df_clean[col] = clean_numeric(df_clean[col])
        
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        df_clean['Risk_Amount'] = df_clean['Risk_Amount'].abs()
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]

        return df_clean.sort_values('Date'), None

    except Exception as e:
        return None, f"讀取期望值失敗: {e}"

def get_daily_report_data(xls, target_month_str=None):
    """
    資料源 B: 讀取 '日報表' 分頁 (用於顯示精確的日曆損益)
    策略：
    1. 尋找名稱包含 '日報表' 的分頁
    2. 讀取 header=4 (第5列)
    3. 鎖定 A欄(日期) 與 H欄(日總計)
    """
    # 尋找分頁：如果有指定月份(例如 '2025-12')就找對應的，否則找最近的一個 '日報表'
    sheet_names = xls.sheet_names
    target_sheet = None
    
    # 優先找符合 '日報表YYYY-MM' 格式的分頁
    daily_sheets = [s for s in sheet_names if "日報表" in s]
    if not daily_sheets:
        return None, "找不到含有 '日報表' 的分頁"
    
    # 簡單邏輯：預設拿最後一個找到的日報表 (通常是最新的)
    # 如果您希望它能跟著下拉選單變動，這裡需要更複雜的邏輯，
    # 但目前我們先抓最新的那張表來呈現。
    target_sheet = daily_sheets[-1] 

    try:
        # [關鍵] 依據您的檔案結構，標題在第 5 列 (header=4)
        df = pd.read_excel(xls, sheet_name=target_sheet, header=4)
        
        # 檢查欄位 (日報表結構通常固定)
        # 假設 A欄是日期，H欄是日總計
        # 為了保險，我們先用 iloc 取位置
        if df.shape[1] < 8:
            return None, f"分頁 '{target_sheet}' 欄位不足，無法讀取日總計。"
            
        # 鎖定 A欄 (Date) 和 H欄 (Daily PnL)
        # 注意：Excel 讀進來後，若 A 欄沒標題可能會變成 Unnamed: 0，我們直接重新命名
        df_cal = df.iloc[:, [0, 7]].copy() # Col 0=日期, Col 7=H欄(日總計)
        df_cal.columns = ['Date', 'DayPnL']
        
        # 清洗數據
        df_cal = df_cal.dropna(subset=['Date'])
        # 過濾掉非日期的列 (例如最下面的總計、平均等文字列)
        df_cal['Date'] = pd.to_datetime(df_cal['Date'], errors='coerce')
        df_cal = df_cal.dropna(subset=['Date'])
        df_cal['Date'] = df_cal['Date'].dt.normalize()
        
        df_cal['DayPnL'] = clean_numeric(df_cal['DayPnL'])
        df_cal = df_cal.fillna(0) # 若損益是空值補0
        
        return df_cal.sort_values('Date'), None, target_sheet

    except Exception as e:
        return None, f"讀取日報表失敗: {e}", target_sheet

def calculate_streaks(df):
    pnl = df['PnL'].values
    max_win_streak = 0
    max_loss_streak = 0
    curr_win = 0
    curr_loss = 0
    for val in pnl:
        if val > 0:
            curr_win += 1
            curr_loss = 0
            if curr_win > max_win_streak: max_win_streak = curr_win
        elif val <= 0:
            curr_loss += 1
            curr_win = 0
            if curr_loss > max_loss_streak: max_loss_streak = curr_loss
    return max_win_streak, max_loss_streak

def calculate_r_squared(df):
    if len(df) < 2: return 0
    y = df['R'].cumsum().values
    x = np.arange(len(y))
    if len(x) != len(y): return 0
    correlation_matrix = np.corrcoef(x, y)
    correlation_xy = correlation_matrix[0, 1]
    r_squared = correlation_xy ** 2
    return r_squared

def calculate_kpis(df):
    total_trades = len(df)
    if total_trades == 0: return None
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    gross_profit = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    total_pnl = df['PnL'].sum()
    total_risk = df['Risk_Amount'].sum()
    win_rate = len(wins) / total_trades if total_trades > 0 else 0
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    full_kelly = (win_rate - (1 - win_rate) / payoff_ratio) if payoff_ratio > 0 else 0
    
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    return {
        "Total Trades": total_trades, "Total PnL": total_pnl, "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio, "Expectancy Custom": expectancy_custom,
        "Profit Factor": profit_factor, "Max Win Streak": max_win,
        "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def generate_calendar_html(year, month, pnl_dict):
    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)
    html = f"""
<style>
    .cal-container {{ font-family: "Source Sans Pro", sans-serif; width: 100%; }}
    .cal-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    .cal-th {{ text-align: center; color: #888; font-size: 12px; padding: 5px 0; border-bottom: 1px solid #eee; }}
    .cal-td {{ height: 90px; vertical-align: top; border: 1px solid #f0f0f0; padding: 4px; position: relative; }}
    .day-num {{ font-size: 12px; color: #999; margin-bottom: 2px; }}
    .day-pnl {{ font-size: 14px; font-weight: bold; text-align: right; position: absolute; bottom: 5px; right: 5px; }}
    .win-bg {{ background-color: #ecfdf5; color: #059669; }}
    .loss-bg {{ background-color: #fef2f2; color: #dc2626; }}
    .neutral-bg {{ background-color: #ffffff; color: #ccc; }}
</style>
<div class="cal-container"><table class="cal-table"><thead><tr>
<th class="cal-th">SUN</th><th class="cal-th">MON</th><th class="cal-th">TUE</th><th class="cal-th">WED</th><th class="cal-th">THU</th><th class="cal-th">FRI</th><th class="cal-th">SAT</th>
</tr></thead><tbody>
"""
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='background-color: #fafafa;'></td>"
                continue
            date_key = f"{year}-{month:02d}-{day:02d}"
            day_pnl = pnl_dict.get(date_key, 0)
            # 只有當該日期在字典中且損益不為0時，才視為有交易 (避免日報表空行顯示 $0)
            has_trade = (date_key in pnl_dict) and (day_pnl != 0)
            
            bg_class = "neutral-bg"
            pnl_text = ""
            if has_trade:
                if day_pnl > 0:
                    bg_class = "win-bg"
                    pnl_text = f"+${day_pnl:,.0f}"
                elif day_pnl < 0:
                    bg_class = "loss-bg"
                    pnl_text = f"-${abs(day_pnl):,.0f}"
                else:
                    pnl_text = "$0"
            html += f"<td class='cal-td {bg_class}'><div class='day-num'>{day}</div><div class='day-pnl'>{pnl_text}</div></td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html

# ==========================================
# 2. 主顯示邏輯
# ==========================================

def display_expectancy_lab(xls):
    # 1. 讀取 KPI 資料 (來源：期望值分頁)
    df_kpi, err_kpi = get_expectancy_data(xls)
    
    # 2. 讀取 日曆 資料 (來源：日報表分頁)
    df_cal, err_cal, sheet_name_cal = get_daily_report_data(xls)

    # 錯誤處理
    if err_kpi:
        st.warning(f"⚠️ KPI 資料讀取警示: {err_kpi}")
    if df_kpi is None or df_kpi.empty:
        st.info("尚未有足夠的交易紀錄可供分析 KPI。")
        return

    # 計算 KPI
    kpi = calculate_kpis(df_kpi)
    
    # --- Row 1: KPI ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}")
    c2.metric("期望值 (Exp)", f"{kpi['Expectancy Custom']:.2f} R")
    pf = kpi['Profit Factor']
    c3.metric("獲利因子 (PF)", f"{pf:.2f}", delta=">1.5 佳" if pf>1.5 else None)
    c4.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    c5.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    st.markdown("---")
    
    # --- Row 2: KPI ---
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="High", delta_color="normal")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="Risk", delta_color="inverse")
    r2 = kpi['R Squared']
    d4.metric("曲線穩定度 (R²)", f"{r2:.2f}")
    d5.empty()
    st.markdown("---")

    # --- 資金管理 ---
    with st.expander("🎰 資金管理控制台 (Kelly Criterion)", expanded=True):
        k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
        with k1: capital = st.number_input("目前本金", value=300000, step=10000)
        with k2: kelly_frac = st.selectbox("凱利倍數", [1.0, 0.5, 0.25, 0.1], index=2, format_func=lambda x: f"Full ({x})" if x==1 else f"Fractional ({x})")
        adj_kelly = max(0, kpi['Full Kelly'] * kelly_frac)
        risk_amt = capital * adj_kelly
        k3.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
        k4.metric("建議單筆風險", f"${risk_amt:,.0f}")
    st.markdown("---")

    # --- 月曆儀表板 (使用日報表資料) ---
    st.markdown(f"#### 📅 交易月曆 (來源: {sheet_name_cal if sheet_name_cal else '無資料'})")
    
    if df_cal is not None and not df_cal.empty:
        # 轉換為字典 { 'YYYY-MM-DD': 損益 }
        df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
        # 如果同一天有多筆(例如多策略)，加總起來
        daily_pnl_series = df_cal.groupby('DateStr')['DayPnL'].sum()
        pnl_dict = daily_pnl_series.to_dict()
        
        # 取得資料中存在的月份 (這裡通常只有日報表的那一個月)
        unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
        
        if len(unique_months) > 0:
            sel_col, _ = st.columns([1, 4]) 
            with sel_col:
                selected_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector')
            
            y, m = selected_period.year, selected_period.month
            
            # 統計當月數據
            month_prefix = f"{y}-{m:02d}"
            month_data = daily_pnl_series[daily_pnl_series.index.str.startswith(month_prefix)]
            
            cal_col, stat_col = st.columns([3, 1])
            with cal_col:
                st.markdown(f"**{selected_period.strftime('%B %Y')}**")
                # 傳入來自日報表的 pnl_dict
                cal_html = generate_calendar_html(y, m, pnl_dict)
                st.markdown(cal_html, unsafe_allow_html=True)
                
            with stat_col:
                st.markdown("##### 當月統計")
                m_pnl = month_data.sum()
                m_max_win = month_data.max() if not month_data.empty and month_data.max() > 0 else 0
                m_max_loss = month_data.min() if not month_data.empty and month_data.min() < 0 else 0
                m_win_days = (month_data > 0).sum()
                m_loss_days = (month_data < 0).sum()
                
                with st.container():
                    st.metric("月損益", f"${m_pnl:,.0f}", delta="本月成果")
                    st.divider()
                    st.metric("單日最大賺", f"${m_max_win:,.0f}", delta_color="normal")
                    st.metric("單日最大賠", f"${m_max_loss:,.0f}", delta_color="inverse")
                    st.divider()
                    st.write(f"📈 獲利天數: **{m_win_days}**")
                    st.write(f"📉 虧損天數: **{m_loss_days}**")
        else:
            st.info("日報表中無有效月份資料。")
    else:
        st.warning(f"⚠️ 無法讀取日報表資料，請確認檔案中是否有 '日報表' 分頁且格式正確。錯誤訊息: {err_cal}")
