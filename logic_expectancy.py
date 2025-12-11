import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go

# ==========================================
# 0. UI 風格與 CSS 注入器 (回歸純淨版)
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        
        /* 全局置中 */
        .block-container { text-align: center; }
        h1, h2, h3, p { text-align: center !important; }

        /* Metric 卡片樣式 (最穩定的寫法) */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
            text-align: center;
            transition: transform 0.2s;
            height: 100%; /* 確保高度一致 */
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        
        div[data-testid="stMetric"]:hover {
            border-color: #81C7D4;
            transform: translateY(-3px);
            box-shadow: 0 10px 15px rgba(0, 0, 0, 0.05);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 14px;
            color: #888;
            justify-content: center;
            width: 100%;
        }

        div[data-testid="stMetricValue"] {
            font-size: 26px;
            font-weight: 600;
            color: #333;
        }

        /* 日曆表格樣式 */
        .cal-table { width: 100%; border-collapse: separate; border-spacing: 6px; margin: 0 auto; }
        .cal-th { text-align: center; color: #aaa; font-size: 11px; font-weight: 400; padding: 10px 0; }
        .cal-td { 
            height: 80px; width: 14%; vertical-align: middle; 
            border-radius: 12px; background-color: #fff; color: #333;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); border: 1px solid #f1f1f1;
            transition: all 0.2s;
            position: relative;
        }
        .cal-td:hover { border-color: #81C7D4; transform: translateY(-2px); }
        .day-content { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; }
        .day-num { font-size: 12px; color: #bbb; margin-bottom: 4px; }
        .day-pnl { font-size: 13px; font-weight: 600; }
        
        /* 隱藏 Plotly 工具列 */
        .modebar { display: none !important; }
        
        /* Selectbox 文字靠左 */
        .cal-selector div[data-baseweb="select"] { text-align: left; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return "plotly_white"

# ==========================================
# 1. 資料處理與計算函式
# ==========================================

def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到含有 '期望值' 的分頁"
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        if df.shape[1] < 14: return None, "期望值表格欄位不足 14 欄"
        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']
        df_clean['Date'] = df_clean['Date'].ffill() 
        df_clean = df_clean.dropna(subset=['Strategy', 'Date'])
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.normalize()
        for col in ['Risk_Amount', 'PnL', 'R']: df_clean[col] = clean_numeric(df_clean[col])
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]
        return df_clean.sort_values('Date'), None
    except Exception as e: return None, f"讀取期望值失敗: {e}"

def get_daily_report_data(xls):
    sheet_names = xls.sheet_names
    daily_sheets = [s for s in sheet_names if "日報表" in s]
    if not daily_sheets: return None, "找不到 '日報表'", "無"
    daily_sheets.sort(reverse=True)
    target_sheets = daily_sheets[:2]
    all_dfs = []
    for sheet in target_sheets:
        try:
            df = pd.read_excel(xls, sheet_name=sheet, header=4)
            if df.shape[1] < 8: continue 
            df_cal = df.iloc[:, [0, 7]].copy() 
            df_cal.columns = ['Date', 'DayPnL']
            df_cal['Date'] = pd.to_datetime(df_cal['Date'], errors='coerce').dt.normalize()
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['DayPnL'] = clean_numeric(df_cal['DayPnL']).fillna(0)
            all_dfs.append(df_cal)
        except: continue
    if not all_dfs: return None, "無效數據", "無"
    return pd.concat(all_dfs, ignore_index=True).sort_values('Date'), None, ""

def calculate_streaks(df):
    pnl = df['PnL'].values
    max_win = max_loss = curr_win = curr_loss = 0
    for val in pnl:
        if val > 0: curr_win += 1; curr_loss = 0; max_win = max(max_win, curr_win)
        elif val <= 0: curr_loss += 1; curr_win = 0; max_loss = max(max_loss, curr_loss)
    return max_win, max_loss

def calculate_r_squared(df):
    if len(df) < 2: return 0
    y = df['R'].cumsum().values; x = np.arange(len(y))
    return (np.corrcoef(x, y)[0, 1]) ** 2

def calculate_kpis(df):
    total = len(df); wins = df[df['PnL'] > 0]; losses = df[df['PnL'] <= 0]
    total_pnl = df['PnL'].sum(); win_rate = len(wins) / total if total > 0 else 0
    
    # 邏輯: 使用 R 來計算盈虧比
    avg_win_r = df[df['R'] > 0]['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = abs(df[df['R'] <= 0]['R'].mean()) if len(losses) > 0 else 0
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    
    # 獲利因子維持用金額計算
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    
    # 期望值邏輯: 總損益 / 總初始風險
    total_risk = df['Risk_Amount'].sum()
    exp_custom = total_pnl / total_risk if total_risk > 0 else 0
    
    # 凱利公式使用 R 盈虧比
    full_kelly = (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    
    max_win, max_loss = calculate_streaks(df); r_sq = calculate_r_squared(df)
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, "Profit Factor": pf, "Expectancy": exp_custom,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def generate_calendar_html(year, month, pnl_dict):
    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(year, month)
    
    win_bg, win_txt = "#e0f7fa", "#006064"; loss_bg, loss_txt = "#ffebee", "#c62828"
    
    html = "<table class='cal-table'><thead><tr>" + "".join([f"<th class='cal-th'>{d}</th>" for d in ["SUN","MON","TUE","WED","THU","FRI","SAT"]]) + "</tr></thead><tbody>"
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0: html += "<td class='cal-td' style='border:none; box-shadow:none;'></td>"; continue
            date_key = f"{year}-{month:02d}-{day:02d}"
            day_pnl = pnl_dict.get(date_key, 0)
            style, pnl_text = "", "-"
            if date_key in pnl_dict and day_pnl != 0:
                style = f"background-color: {win_bg}; color: {win_txt};" if day_pnl > 0 else f"background-color: {loss_bg}; color: {loss_txt};"
                pnl_text = f"{'+' if day_pnl>0 else '-'}${abs(day_pnl):,.0f}"
            html += f"<td class='cal-td' style='{style}'><div class='day-content'><div class='day-num'>{day}</div><div class='day-pnl'>{pnl_text}</div></div></td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# ==========================================
# 2. UI 元件 (Fragments)
# ==========================================

@st.fragment
def draw_kpi_cards(kpi):
    # Tooltip 定義 (更新版)
    tips = {
        "Exp": "定義: 每單位風險的平均獲利。\n公式: 總損益 ÷ 總初始風險",
        "PF": "定義: 總獲利金額與總虧損金額的比率 (Gross Win / Gross Loss)。",
        "Payoff": "定義: 平均每筆獲利 R 與平均每筆虧損 R 的比例。\n公式: Avg Win R ÷ Avg Loss R",
        "Win": "定義: 獲利交易次數佔總交易次數的比例。",
        "RSQ": "定義: 權益曲線的回歸判定係數，越接近 1 代表獲利越穩定。"
    }

    # 第一排
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益", f"${kpi['Total PnL']:,.0f}")
    c2.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=tips['Exp'])
    c3.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=tips['PF'])
    c4.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=tips['Payoff'])
    c5.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=tips['Win'])

    st.write("") # 間距

    # 第二排
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    d4.metric("穩定度 R²", f"{kpi['R Squared']:.2f}", help=tips['RSQ'])
    d5.empty()

@st.fragment
def draw_kelly_fragment(kpi):
    st.markdown("<h4 style='text-align: center; color: #888; margin-top: 20px;'>Position Sizing (Kelly)</h4>", unsafe_allow_html=True)
    c_center = st.columns([1, 2, 2, 2, 2, 1]) 
    
    with c_center[1]: capital = st.number_input("目前本金", value=300000, step=10000)
    with c_center[2]: 
        fraction_options = [1/4, 1/5, 1/6, 1/7, 1/8]
        kelly_frac = st.selectbox("凱利倍數", fraction_options, index=1, format_func=lambda x: f"1/{int(1/x)} Kelly")
        
    win_rate = kpi.get('Win Rate', 0)
    payoff_r = kpi.get('Payoff Ratio', 0)
    full_kelly_val = kpi.get('Full Kelly', 0)
    adj_kelly = max(0, full_kelly_val * kelly_frac)
    risk_amt = capital * adj_kelly
    
    help_text = f"""
    公式: K = W - ( (1-W) / R )
    • 勝率 (W): {win_rate*100:.1f}%
    • 盈虧比 (R): {payoff_r:.2f}
    完整凱利: {full_kelly_val*100:.2f}%
    建議 ({int(1/kelly_frac)}分之1): {adj_kelly*100:.2f}%
    """
    with c_center[3]: st.metric("建議倉位 %", f"{adj_kelly*100:.2f}%", help=help_text)
    with c_center[4]: st.metric("建議單筆風險", f"${risk_amt:,.0f}")

@st.fragment
def draw_calendar_fragment(df_cal, theme_mode):
    if df_cal is None or df_cal.empty:
        st.warning("無日報表資料"); return

    df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
    daily_pnl = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    
    if len(unique_months) == 0: st.info("無有效月份"); return

    st.markdown("---")
    
    c_header_left, c_header_space = st.columns([1, 4])
    with c_header_left:
        st.markdown('<div class="cal-selector">', unsafe_allow_html=True)
        sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    y, m = sel_period.year, sel_period.month
    month_data = df_cal[df_cal['Date'].dt.to_period('M') == sel_period]
    month_pnl_series = month_data['DayPnL']
    
    m_total_pnl = month_pnl_series.sum()
    wins, losses = month_pnl_series[month_pnl_series > 0], month_pnl_series[month_pnl_series < 0]
    day_max_win = wins.max() if not wins.empty else 0
    day_max_loss = losses.min() if not losses.empty else 0
    
    c_cal, c_stat = st.columns([3, 1])
    with c_cal:
        st.markdown(f"<h3 style='margin-bottom: 20px; text-align: left !important; padding-left: 10px;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)
        st.markdown(generate_calendar_html(y, m, daily_pnl), unsafe_allow_html=True)
        
    with c_stat:
        st.markdown("#### 月度摘要")
        st.metric("本月淨損益", f"${m_total_pnl:,.0f}")
        st.metric("日最大獲利", f"+${day_max_win:,.0f}")
        st.metric("日最大虧損", f"-${abs(day_max_loss):,.0f}")
        st.write(f"📈 獲利: **{len(wins)}** 天")
        st.write(f"📉 虧損: **{len(losses)}** 天")

# ==========================================
# 3. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    chart_theme = inject_custom_css()
    st.markdown("<h1>TRADING PERFORMANCE</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #999; margin-bottom: 40px;'>現代極簡交易儀表板</p>", unsafe_allow_html=True)

    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, err_cal, _ = get_daily_report_data(xls)

    if err_kpi: st.warning(f"KPI 讀取錯誤: {err_kpi}"); return
    if df_kpi is None or df_kpi.empty: st.info("無資料"); return

    # 計算
    kpi = calculate_kpis(df_kpi)

    # 1. KPI 區塊 (純卡片，無圖表按鈕)
    draw_kpi_cards(kpi)
    
    st.markdown("---")
    
    # 2. 凱利公式
    draw_kelly_fragment(kpi)
    
    # 3. 日曆
    draw_calendar_fragment(df_cal, chart_theme)
