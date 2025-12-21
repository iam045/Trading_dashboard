import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go

# ==========================================
# 0. UI 風格與 CSS 注入器 (集中管理樣式)
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; max-width: 1400px; padding-top: 2rem; }
        
        h1, h2, h3, p { text-align: center !important; }

        /* --- Metric 卡片容器 --- */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 15px 10px 15px;
            min-height: 180px; 
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        div[data-testid="column"]:has(div[data-testid="stMetric"]):hover {
            border-color: #81C7D4;
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08);
        }

        /* --- Metric 數值文字 --- */
        div[data-testid="stMetric"] { background-color: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
        div[data-testid="stMetricLabel"] { font-size: 13px; color: #888; justify-content: center; width: 100%; }
        div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; color: #333; margin-bottom: 5px; }

        /* --- 全域元件微調 --- */
        .stTabs [data-baseweb="tab-list"] { justify-content: flex-start !important; gap: 20px; }
        .modebar { display: none !important; } 

        /* --- 日曆表格樣式 (9欄佈局) --- */
        .cal-container { width: 100%; overflow-x: auto; margin-top: 20px; }
        .cal-table { 
            width: 100%; 
            min-width: 1200px; 
            border-collapse: separate; 
            border-spacing: 6px; 
            margin: 0 auto; 
            table-layout: fixed; 
        }
        .cal-th { padding-bottom: 10px; color: #888; font-size: 13px; font-weight: 500; text-transform: uppercase; }
        .cal-td { 
            height: 90px; 
            vertical-align: top;
            border-radius: 10px; 
            background-color: #fff; 
            color: #333;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); 
            border: 1px solid #f1f1f1;
            padding: 8px;
            position: relative;
            transition: all 0.2s;
        }
        .cal-td:hover { border-color: #81C7D4; transform: translateY(-2px); }
        .day-num { font-size: 14px; color: #aaa; position: absolute; top: 8px; right: 10px; font-weight: bold; }
        .day-pnl { margin-top: 22px; font-size: 15px; font-weight: 700; text-align: center; }
        .day-info { font-size: 11px; color: inherit; opacity: 0.8; text-align: center; margin-top: 2px; }

        .summary-td { width: 150px; vertical-align: middle; background-color: transparent !important; border: none !important; padding-left: 10px !important; }
        .week-card { background-color: #fff; border-radius: 12px; padding: 10px; text-align: center; border: 1px solid #e0e0e0; height: 80px; display: flex; flex-direction: column; justify-content: center; }
        .week-title { font-size: 12px; color: #81C7D4; font-weight: bold; margin-bottom: 4px; }
        .week-pnl { font-size: 18px; font-weight: 700; }
        .month-card { background-color: #fff; border-radius: 12px; padding: 10px; text-align: center; border-left: 4px solid #81C7D4; height: 80px; display: flex; flex-direction: column; justify-content: center; }
        .month-title { font-size: 13px; font-weight: 600; color: #555; }
        .month-val { font-size: 20px; font-weight: 800; color: #000 !important; }

        .text-green { color: #00897b; }
        .text-red { color: #e53935; }
        .bg-green { background-color: #e0f2f1 !important; border-color: #b2dfdb !important; color: #004d40 !important; }
        .bg-red { background-color: #ffebee !important; border-color: #ffcdd2 !important; color: #b71c1c !important; }
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
        for col in ['Risk_Amount', 'PnL', 'R']: 
            df_clean[col] = clean_numeric(df_clean[col])
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
    """計算權益曲線 R平方 (穩定度)"""
    if len(df) < 2: return 0
    y = df['R'].cumsum().values; x = np.arange(len(y))
    return (np.corrcoef(x, y)[0, 1]) ** 2

def calculate_kpis(df):
    total = len(df); wins = df[df['PnL'] > 0]; losses = df[df['PnL'] <= 0]
    total_pnl = df['PnL'].sum(); win_rate = len(wins) / total if total > 0 else 0
    avg_win_r = df[df['R'] > 0]['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = abs(df[df['R'] <= 0]['R'].mean()) if len(losses) > 0 else 0
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    exp_custom = total_pnl / df['Risk_Amount'].sum() if df['Risk_Amount'].sum() > 0 else 0
    full_kelly = (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    max_win, max_loss = calculate_streaks(df); r_sq = calculate_r_squared(df)
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, "Profit Factor": pf, "Expectancy": exp_custom,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def calculate_trends(df):
    """計算累積數據供圖表使用 (修正 R2 邏輯)"""
    df = df.sort_values('Date').reset_index(drop=True).copy()
    df['win_r_val'] = df['R'].apply(lambda x: x if x > 0 else 0)
    df['loss_r_val'] = df['R'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    
    s_pnl = df['PnL'].cumsum()
    s_risk = df['Risk_Amount'].cumsum()
    s_r_cumsum = df['R'].cumsum() # [關鍵] 用於計算穩定度走勢
    s_win_r = df['win_r_val'].cumsum()
    s_loss_r = df['loss_r_val'].cumsum()
    s_win_count = df['is_win'].cumsum()
    s_loss_count = (df.index + 1) - s_win_count
    s_g_win = df['PnL'].apply(lambda x: x if x > 0 else 0).cumsum()
    s_g_loss = df['PnL'].apply(lambda x: abs(x) if x <= 0 else 0).cumsum()

    df['Total PnL'] = s_pnl
    df['Expectancy'] = s_pnl / s_risk.replace(0, np.nan)
    df['Profit Factor'] = (s_g_win / s_g_loss.replace(0, np.nan)).fillna(10).clip(upper=10)
    df['Payoff Ratio'] = (s_win_r / s_win_count) / (s_loss_r / s_loss_count).replace(0, np.nan)
    
    # [修正] 改用累積 R 進行相關性計算，與卡片的 0.65 同步
    df['R Squared'] = s_r_cumsum.expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
    
    return df.fillna(0)

# ==========================================
# 2. 繪圖與 UI 元件 (Fragments)
# ==========================================

def hex_to_rgba(hex_color, opacity=0.1):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {opacity})"

def get_sparkline(df_t, col_name, color):
    fill_color = hex_to_rgba(color, 0.1)
    df_show = df_t.tail(50) if len(df_t) > 50 else df_t
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_show['Date'], y=df_show[col_name], mode='lines', line=dict(color=color, width=2), fill='tozeroy', fillcolor=fill_color, hoverinfo='y'))
    fig.update_layout(height=60, margin=dict(l=0, r=0, t=5, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    return fig

@st.fragment
def draw_kpi_cards_with_charts(kpi, df_t):
    tips = {
        "Exp": "期望值 (Expectancy):\n每承擔 1R 風險，預期能賺回多少 R。",
        "PF": "獲利因子 (Profit Factor):\n總獲利金額是總虧損金額的幾倍。",
        "Payoff": "盈虧比 (Payoff Ratio):\n平均賺的一筆是平均賠的一筆的幾倍。",
        "Win": "勝率 (Win Rate):\n獲利交易次數 ÷ 總交易次數",
        "RSQ": "穩定度 R Squared:\n權益曲線的平滑程度，目前使用 R (風險倍數) 計算，反映交易邏輯的一致性。"
    }
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("總損益", f"${kpi['Total PnL']:,.0f}"); st.write("") 
    with c2: 
        st.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=tips['Exp'])
        st.plotly_chart(get_sparkline(df_t, 'Expectancy', '#FF8A65'), use_container_width=True, config={'displayModeBar': False})
    with c3: 
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=tips['PF'])
        st.plotly_chart(get_sparkline(df_t, 'Profit Factor', '#BA68C8'), use_container_width=True, config={'displayModeBar': False})
    with c4: 
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=tips['Payoff'])
        st.plotly_chart(get_sparkline(df_t, 'Payoff Ratio', '#4DB6AC'), use_container_width=True, config={'displayModeBar': False})
    with c5: st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=tips['Win']); st.write("") 

    st.write("") 
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    with d4:
        st.metric("穩定度 R²", f"{kpi['R Squared']:.2f}", help=tips['RSQ'])
        st.plotly_chart(get_sparkline(df_t, 'R Squared', '#9575CD'), use_container_width=True, config={'displayModeBar': False})
    d5.empty()

@st.fragment
def draw_kelly_fragment(kpi):
    st.markdown("<h4 style='text-align: center; color: #888; margin-top: 10px;'>Position Sizing (Kelly)</h4>", unsafe_allow_html=True)
    c_center = st.columns([1, 2, 2, 2, 2, 1]) 
    with c_center[1]: capital = st.number_input("目前本金", value=300000, step=10000)
    with c_center[2]: kelly_frac = st.selectbox("凱利倍數", [1/4, 1/5, 1/6, 1/7, 1/8], index=1, format_func=lambda x: f"1/{int(1/x)} Kelly")
    adj_kelly = max(0, kpi['Full Kelly'] * kelly_frac)
    with c_center[3]: st.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
    with c_center[4]: st.metric("建議單筆風險", f"${capital * adj_kelly:,.0f}")

@st.fragment
def draw_calendar_fragment(df_cal, theme_mode):
    if df_cal is None or df_cal.empty: return
    df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
    daily_pnl_map = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    
    st.markdown("---")
    c_header_left, _ = st.columns([1, 4])
    with c_header_left: sel_period = st.selectbox("選擇月份", unique_months, index=0, label_visibility="collapsed")
    
    y, m = sel_period.year, sel_period.month
    df_month = df_cal[(df_cal['Date'].dt.year == y) & (df_cal['Date'].dt.month == m)].sort_values('Date') 
    
    if not df_month.empty:
        df_month['CumPnL'] = df_month['DayPnL'].cumsum()
        c1, c2 = st.columns(2)
        fig1 = go.Figure(go.Scatter(x=df_month['Date'], y=df_month['CumPnL'], mode='lines', line=dict(color='#ef5350' if df_month['DayPnL'].sum() >= 0 else '#26a69a', width=3), fill='tozeroy'))
        fig1.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        with c1: st.plotly_chart(fig1, use_container_width=True)
        fig2 = go.Figure(go.Bar(x=df_month['Date'], y=df_month['DayPnL'], marker_color=['#ef5350' if v >= 0 else '#26a69a' for v in df_month['DayPnL']]))
        fig2.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        with c2: st.plotly_chart(fig2, use_container_width=True)

    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(y, m)
    
    html = """<div class="cal-container"><table class='cal-table'><thead><tr><th class='cal-th'>Sun</th><th class='cal-th'>Mon</th><th class='cal-th'>Tue</th><th class='cal-th'>Wed</th><th class='cal-th'>Thu</th><th class='cal-th'>Fri</th><th class='cal-th'>Sat</th><th class='cal-th'></th><th class='cal-th'></th></tr></thead><tbody>"""
    
    week_count = 1
    m_pnl = df_month['DayPnL'].sum()
    df_active = df_month[df_month['DayPnL'] != 0]
    m_win_rate = (len(df_active[df_active['DayPnL'] > 0]) / len(df_active)) if len(df_active) > 0 else 0
    stats = [{"t": "本月淨損益", "v": f"${m_pnl:,.0f}"}, {"t": "本月日勝率", "v": f"{m_win_rate*100:.1f}%"}, {"t": "日最大獲利", "v": f"${df_active['DayPnL'].max() if not df_active.empty else 0:,.0f}"}, {"t": "日最大虧損", "v": f"${df_active['DayPnL'].min() if not df_active.empty else 0:,.0f}"}]

    for idx, week in enumerate(month_days):
        html += "<tr>"
        wpnl = 0
        for day in week:
            if day == 0: html += "<td class='cal-td' style='background:transparent;border:none;'></td>"
            else:
                pnl = daily_pnl_map.get(f"{y}-{m:02d}-{day:02d}", 0)
                wpnl += pnl
                cls = "cal-td " + ("bg-green" if pnl > 0 else "bg-red" if pnl < 0 else "")
                pnl_txt = f"<div class='day-pnl'>{'+' if pnl>0 else '-'}${abs(pnl):,.0f}</div>" if pnl != 0 else ""
                html += f"<td class='{cls}'><div class='day-num'>{day}</div>{pnl_txt}</td>"
        
        # 週與月統計格
        html += f"<td class='summary-td'><div class='week-card'><div class='week-title'>Week {week_count}</div><div class='week-pnl {'text-green' if wpnl>=0 else 'text-red'}'>${abs(wpnl):,.0f}</div></div></td>"
        if idx < len(stats): html += f"<td class='summary-td'><div class='month-card'><div class='month-title'>{stats[idx]['t']}</div><div class='month-val'>{stats[idx]['v']}</div></div></td>"
        else: html += "<td class='summary-td'></td>"
        html += "</tr>"; week_count += 1

    st.markdown(html + "</tbody></table></div>", unsafe_allow_html=True)

# ==========================================
# 3. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    chart_theme = inject_custom_css()
    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, err_cal, _ = get_daily_report_data(xls)
    if err_kpi: st.warning(f"KPI 讀取錯誤: {err_kpi}"); return
    if df_kpi is None or df_kpi.empty: st.info("無 KPI 資料"); return

    kpi = calculate_kpis(df_kpi)
    df_trends = calculate_trends(df_kpi)
    draw_kpi_cards_with_charts(kpi, df_trends)
    st.markdown("---")
    draw_kelly_fragment(kpi)
    draw_calendar_fragment(df_cal, chart_theme)
