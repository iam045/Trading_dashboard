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
    # 尋找含有 "期望值" 字眼的分頁
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        # 讀取資料 (假設標題在第15列 -> header=14)
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        if df.shape[1] < 14:
            return None, "表格欄位不足 14 欄，請檢查格式。"

        # 欄位選取：日期(0), 策略(1), 最後總風險(10), 損益(11), R(13)
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
    
    # 計算相關係數矩陣
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
    
    # 凱利公式基礎值 (Full Kelly %)
    if payoff_ratio > 0:
        full_kelly = win_rate - (1 - win_rate) / payoff_ratio
    else:
        full_kelly = 0
        
    # 進階數據
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    
    # SQN
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

def generate_calendar_html(year, month, df_daily):
    """
    生成 HTML 格式的月曆 (CSS Grid/Table)
    """
    cal = calendar.Calendar(firstweekday=6) # 星期日開始
    month_days = cal.monthdayscalendar(year, month)
    
    # CSS 樣式
    html = f"""
    <style>
        .cal-container {{ font-family: sans-serif; width: 100%; }}
        .cal-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        .cal-th {{ text-align: center; color: #888; font-size: 12px; padding: 5px 0; }}
        .cal-td {{ 
            height: 80px; /* 格子高度 */
            vertical-align: top; 
            border: 1px solid #eee; 
            padding: 5px; 
            position: relative;
        }}
        .day-num {{ font-size: 12px; color: #333; font-weight: bold; margin-bottom: 4px; }}
        .day-pnl {{ font-size: 14px; font-weight: 600; text-align: right; margin-top: 15px; }}
        
        /* 顏色定義 */
        .win-bg {{ background-color: #dcfce7; color: #166534; }}  /* 淺綠底深綠字 */
        .loss-bg {{ background-color: #fee2e2; color: #991b1b; }} /* 淺紅底深紅字 */
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
            
            # 查找當日損益
            current_date = pd.Timestamp(year, month, day)
            day_pnl = 0
            has_trade = False
            
            if current_date in df_daily.index:
                day_pnl = df_daily.loc[current_date]
                has_trade = True
            
            # 決定樣式
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
            
            html += f"""
                <td class='cal-td {bg_class}'>
                    <div class="day-num">{day}</div>
                    <div class="day-pnl">{pnl_text}</div>
                </td>
            """
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
    
    # ---------------------------------------------------------
    # 1. 頂部核心數據矩陣 (5 x 2 Layout)
    # ---------------------------------------------------------
    st.markdown("### 🏥 系統體檢報告 (System Health)")
    
    # Row 1: 總損益 | 期望值 | 獲利因子 | 盈虧比 | 勝率
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}")
    c2.metric("期望值 (Exp)", f"{kpi['Expectancy Custom']:.2f} R")
    
    pf = kpi['Profit Factor']
    c3.metric("獲利因子 (PF)", f"{pf:.2f}", delta=">1.5 佳" if pf>1.5 else None)
    
    c4.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    c5.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    
    st.markdown("---")
    
    # Row 2: 總交易次數 | 最大連勝 | 最大連敗 | 曲線穩定度 | (空)
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="High", delta_color="normal")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="Risk", delta_color="inverse")
    
    r2 = kpi['R Squared']
    d4.metric("曲線穩定度 (R²)", f"{r2:.2f}", help="越接近 1 代表資金曲線越平滑")
    d5.empty() # 留空
    
    st.markdown("---")

    # ---------------------------------------------------------
    # 2. 資金管理 (凱利公式) - 獨立一列
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 3. 月曆儀表板 (Calendar Dashboard)
    # ---------------------------------------------------------
    st.markdown("#### 📅 交易月曆 (Monthly Performance)")
    
    # 準備日資料
    df['DateOnly'] = df['Date'].dt.date
    # 同一天可能有多筆交易，需加總
    daily_pnl = df.groupby('DateOnly')['PnL'].sum()
    daily_pnl.index = pd.to_datetime(daily_pnl.index)
    
    # 建立月份選擇器 (依資料存在的月份倒序排列)
    if not daily_pnl.empty:
        # 取得所有有交易的月份
        unique_months = daily_pnl.index.to_period('M').unique().sort_values(ascending=False)
        selected_period = st.selectbox("選擇月份", unique_months, index=0)
        
        # 篩選該月資料
        y, m = selected_period.year, selected_period.month
        mask = (daily_pnl.index.year == y) & (daily_pnl.index.month == m)
        month_data = daily_pnl[mask]
        
        # --- 版面配置：左邊日曆 (3份寬)，右邊統計 (1份寬) ---
        cal_col, stat_col = st.columns([3, 1])
        
        with cal_col:
            st.markdown(f"**{selected_period.strftime('%B %Y')}**")
            # 呼叫我們寫的 HTML 生成器
            cal_html = generate_calendar_html(y, m, month_data)
            st.markdown(cal_html, unsafe_allow_html=True)
            
        with stat_col:
            st.markdown("##### 當月統計")
            # 計算當月統計數據
            m_pnl = month_data.sum()
            m_max_win = month_data.max() if not month_data.empty and month_data.max() > 0 else 0
            m_max_loss = month_data.min() if not month_data.empty and month_data.min() < 0 else 0
            m_win_days = (month_data > 0).sum()
            m_loss_days = (month_data < 0).sum()
            
            # 使用 container 讓排版更像卡片
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
