import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import calendar

# ==========================================
# 1. 基礎運算與資料讀取 (Helper Functions)
# ==========================================

def clean_numeric(series):
    """清洗數字格式 (移除逗號、轉型)"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    """讀取 Excel 中的期望值分頁"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        if df.shape[1] < 14:
            return None, "表格欄位不足 14 欄，請檢查格式。"

        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']

        df_clean = df_clean.dropna(subset=['Date']) 
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        
        for col in ['Risk_Amount', 'PnL', 'R']:
            df_clean[col] = clean_numeric(df_clean[col])
        
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        df_clean['Risk_Amount'] = df_clean['Risk_Amount'].abs()
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]

        return df_clean.sort_values('Date'), None

    except Exception as e:
        return None, f"讀取失敗: {e}"

def calculate_streaks(df):
    """計算最大連勝與連敗"""
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
    """計算權益曲線的平滑度 (R-Squared)"""
    if len(df) < 2: return 0
    y = df['R'].cumsum().values
    x = np.arange(len(y))
    correlation_matrix = np.corrcoef(x, y)
    correlation_xy = correlation_matrix[0, 1]
    r_squared = correlation_xy ** 2
    return r_squared

def calculate_kpis(df):
    """計算所有關鍵指標"""
    total_trades = len(df)
    if total_trades == 0: return None
    
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    gross_profit = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    total_pnl = df['PnL'].sum()
    total_risk = df['Risk_Amount'].sum()
    
    win_rate = len(wins) / total_trades
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    expectancy_custom = total_pnl / total_risk if total_risk > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    if payoff_ratio > 0:
        full_kelly = win_rate - (1 - win_rate) / payoff_ratio
    else:
        full_kelly = 0
        
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    
    r_std = df['R'].std()
    sqn = (expectancy_custom / r_std * np.sqrt(total_trades)) if r_std > 0 else 0
    
    return {
        "Total Trades": total_trades,
        "Total PnL": total_pnl,
        "Win Rate": win_rate,
        "Payoff Ratio": payoff_ratio,
        "Expectancy Custom": expectancy_custom,
        "Profit Factor": profit_factor,
        "Max Win Streak": max_win,
        "Max Loss Streak": max_loss,
        "R Squared": r_sq,
        "Full Kelly": full_kelly,
        "SQN": sqn
    }

def generate_calendar_html(year, month, pnl_dict):
    """
    生成 HTML 格式的月曆
    修正重點：
    1. 接收 pnl_dict (Key為 'YYYY-MM-DD' 字串)，解決日期比對錯誤問題
    2. 移除縮排避免 Markdown 解析錯誤
    """
    cal = calendar.Calendar(firstweekday=6) # 星期日開始
    month_days = cal.monthdayscalendar(year, month)
    
    # CSS
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
<div class="cal-container">
    <table class="cal-table">
        <thead>
            <tr>
                <th class="cal-th">SUN</th><th class="cal-th">MON</th><th class="cal-th">TUE</th>
                <th class="cal-th">WED</th><th class="cal-th">THU</th><th class="cal-th">FRI</th>
                <th class="cal-th">SAT</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='background-color: #fafafa;'></td>"
                continue
            
            # 使用字串 Key 進行精確查找 (解決第二週後的 Bug)
            date_key = f"{year}-{month:02d}-{day:02d}"
            day_pnl = pnl_dict.get(date_key, 0)
            has_trade = date_key in pnl_dict
            
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
# 2. 主顯示邏輯 (Dashboard UI)
# ==========================================

def display_expectancy_lab(xls):
    df, err = get_expectancy_data(xls)
    
    if err:
        st.warning(f"⚠️ {err}")
        return
    if df is None or df.empty:
        st.info("尚未有足夠的交易紀錄可供分析。")
        return

    kpi = calculate_kpis(df)
    
    # --- Row 1: 5欄位 ---
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}")
    c2.metric("期望值 (Exp)", f"{kpi['Expectancy Custom']:.2f} R")
    pf = kpi['Profit Factor']
    c3.metric("獲利因子 (PF)", f"{pf:.2f}", delta=">1.5 佳" if pf>1.5 else None)
    c4.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    c5.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    
    st.markdown("---")
    
    # --- Row 2: 5欄位 ---
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="High", delta_color="normal")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="Risk", delta_color="inverse")
    r2 = kpi['R Squared']
    d4.metric("曲線穩定度 (R²)", f"{r2:.2f}", help="越接近 1 代表資金曲線越平滑")
    d5.empty()
    
    st.markdown("---")

    # --- 資金管理 ---
    with st.expander("🎰 資金管理控制台 (Kelly Criterion)", expanded=True):
        k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
        with k1:
            capital = st.number_input("目前本金", value=300000, step=10000)
        with k2:
            kelly_frac = st.selectbox("凱利倍數", [1.0, 0.5, 0.25, 0.1], index=2, 
                                     format_func=lambda x: f"Full ({x})" if x==1 else f"Fractional ({x})")
        adj_kelly = max(0, kpi['Full Kelly'] * kelly_frac)
        risk_amt = capital * adj_kelly
        k3.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
        k4.metric("建議單筆風險", f"${risk_amt:,.0f}")

    st.markdown("---")

    # --- 月曆儀表板 (Calendar Dashboard) ---
    st.markdown("#### 📅 交易月曆 (Monthly Performance)")
    
    # 1. 準備純字串索引的字典，解決日期錯亂問題
    #    格式轉換為 'YYYY-MM-DD'，確保與日曆迴圈完全匹配
    df['DateStr'] = df['Date'].dt.strftime('%Y-%m-%d')
    daily_pnl_series = df.groupby('DateStr')['PnL'].sum()
    pnl_dict = daily_pnl_series.to_dict() # 變成 {'2025-12-01': 500, ...}
    
    # 取得月份列表
    df['DateOnly'] = df['Date'].dt.date # 用於下拉選單排序
    unique_months = pd.to_datetime(df['DateOnly']).dt.to_period('M').unique().sort_values(ascending=False)
    
    if len(unique_months) > 0:
        # 修改點 1: 使用 st.columns 縮短下拉選單寬度
        sel_col, _ = st.columns([1, 4]) 
        with sel_col:
            # 修改點 2: 加入 key='cal_month_selector' 防止隨意重置
            selected_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector')
        
        y, m = selected_period.year, selected_period.month
        
        # 準備當月統計數據 (用於右側)
        # 這裡需要篩選出當月的數據進行計算
        month_mask = (pd.to_datetime(daily_pnl_series.index).year == y) & \
                     (pd.to_datetime(daily_pnl_series.index).month == m)
        month_data = daily_pnl_series[month_mask]
        
        # --- 版面配置 ---
        cal_col, stat_col = st.columns([3, 1])
        
        with cal_col:
            st.markdown(f"**{selected_period.strftime('%B %Y')}**")
            # 呼叫 HTML 生成器，傳入 pnl_dict
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
        st.info("無日資料可顯示")
