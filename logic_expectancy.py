import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 0. UI 風格與 CSS 注入器 (卡片底部按鈕版)
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; }
        h1, h2, h3, p { text-align: center !important; }

        /* --- 1. 卡片容器樣式 --- */
        /* 讓 Column 變成白色卡片 */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 15px 10px 15px; /* 上右下左，下方留少一點給按鈕 */
            text-align: center;
            transition: transform 0.2s;
            display: flex;
            flex-direction: column;
            justify-content: space-between; /* 內容上下撐開 */
            min-height: 160px; /* 稍微加高以容納底部按鈕 */
        }
        div[data-testid="column"]:has(div[data-testid="stMetric"]):hover {
            border-color: #81C7D4;
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.05);
        }

        /* --- 2. Metric 數值樣式 --- */
        div[data-testid="stMetric"] {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        div[data-testid="stMetricLabel"] { 
            font-size: 13px; color: #888; justify-content: center; width: 100%; 
        }
        div[data-testid="stMetricValue"] { 
            font-size: 24px; font-weight: 600; color: #333; 
        }

        /* --- 3. 底部 Popover 按鈕樣式 --- */
        /* 針對在 column 裡面的 stPopover button 進行美化 */
        div[data-testid="column"] div[data-testid="stPopover"] button {
            border: none !important;
            background: transparent !important;
            color: #81C7D4 !important; /* 主題色文字 */
            font-size: 0.85rem !important; /* 字體縮小 */
            width: 100% !important; /* 滿版寬度 */
            padding: 8px 0px !important;
            margin-top: 10px !important;
            border-top: 1px solid #f5f5f5 !important; /* 上方加一條淡線區隔 */
            border-radius: 0px 0px 12px 12px !important; /* 下方圓角 */
            transition: all 0.2s;
        }

        /* 滑鼠移過去的效果 */
        div[data-testid="column"] div[data-testid="stPopover"] button:hover {
            background-color: #f8fdfe !important; /* 極淡的藍色背景 */
            color: #29b6f6 !important;
            border-color: #e0f7fa !important;
        }
        
        div[data-testid="column"] div[data-testid="stPopover"] button:focus,
        div[data-testid="column"] div[data-testid="stPopover"] button:active {
            outline: none !important;
            box-shadow: none !important;
            border: none !important;
            background-color: transparent !important;
        }

        /* --- 日曆與其他樣式 --- */
        .cal-table { width: 100%; border-collapse: separate; border-spacing: 5px; margin: 0 auto; }
        .cal-td { 
            height: 70px; width: 14%; vertical-align: middle; 
            border-radius: 12px; background-color: #fff; color: #333;
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); border: 1px solid #f1f1f1;
            transition: all 0.2s;
        }
        .cal-td:hover { border-color: #81C7D4; transform: translateY(-2px); }
        .day-num { font-size: 12px; color: #bbb; margin-bottom: 2px; }
        .day-pnl { font-size: 13px; font-weight: 600; }
        .modebar { display: none !important; }
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
    
    # R Payoff
    avg_win_r = df[df['R'] > 0]['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = abs(df[df['R'] <= 0]['R'].mean()) if len(losses) > 0 else 0
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    
    # Money PF
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    # Expectancy
    total_risk = df['Risk_Amount'].sum()
    exp_custom = total_pnl / total_risk if total_risk > 0 else 0
    # Kelly
    full_kelly = (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    
    max_win, max_loss = calculate_streaks(df); r_sq = calculate_r_squared(df)
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, "Profit Factor": pf, "Expectancy": exp_custom,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def calculate_trends(df):
    df = df.sort_values('Date').reset_index(drop=True).copy()
    
    # R 趨勢計算 (累計)
    df['win_r_val'] = df['R'].apply(lambda x: x if x > 0 else 0)
    df['loss_r_val'] = df['R'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    
    # Cumulative sums
    s_pnl = df['PnL'].cumsum()
    s_risk = df['Risk_Amount'].cumsum()
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
    df['R Squared'] = s_pnl.expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
    
    return df.fillna(0)

# ==========================================
# 2. 繪圖與 UI 元件 (Fragments)
# ==========================================

def hex_to_rgba(hex_color, opacity=0.1):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {opacity})"
    return hex_color 

def get_mini_chart(df_t, col_name, color, title, height=400):
    fill_color = hex_to_rgba(color, 0.15)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_t['Date'], y=df_t[col_name], 
        mode='lines', name=col_name,
        line=dict(color=color, width=2.5),
        fill='tozeroy', 
        fillcolor=fill_color 
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14), x=0.5, xanchor='center'),
        height=height, 
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=True, gridcolor='#eee'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    return fig

@st.fragment
def draw_kpi_cards_with_charts(kpi, df_t):
    tips = {
        "Exp": "定義: 每單位風險的平均獲利。\n公式: 總損益 ÷ 總初始風險",
        "PF": "定義: 總獲利金額與總虧損金額的比率。\n公式: 總獲利金額 ÷ 總虧損金額",
        "Payoff": "定義: 平均每筆獲利 R 與平均每筆虧損 R 的比例。\n公式: Avg Win R ÷ Avg Loss R",
        "Win": "定義: 獲利交易次數佔總交易次數的比例。\n公式: 獲利筆數 ÷ 總交易筆數",
        "RSQ": "定義: 權益曲線的回歸判定係數，越接近 1 代表獲利越穩定。"
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    
    # 1. 總損益 (純數據)
    with c1:
        st.metric("總損益", f"${kpi['Total PnL']:,.0f}")
        # 若需要佔位符讓高度一致，可以加個空的 container
        st.write("") 

    # 2. 期望值
    with c2:
        st.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=tips['Exp'])
        # 按鈕放在 metric 下方
        with st.popover("📊 期望值", use_container_width=True):
            range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_exp")
            df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
            st.plotly_chart(get_mini_chart(df_show, 'Expectancy', '#FF8A65', '期望值走勢'), use_container_width=True)

    # 3. 獲利因子
    with c3:
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=tips['PF'])
        with st.popover("📊 獲利因子", use_container_width=True):
            range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_pf")
            df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
            st.plotly_chart(get_mini_chart(df_show, 'Profit Factor', '#BA68C8', '獲利因子走勢'), use_container_width=True)

    # 4. 盈虧比
    with c4:
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=tips['Payoff'])
        with st.popover("📊 盈虧比", use_container_width=True):
            range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_payoff")
            df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
            st.plotly_chart(get_mini_chart(df_show, 'Payoff Ratio', '#4DB6AC', '盈虧比走勢'), use_container_width=True)

    # 5. 勝率 (純數據)
    with c5:
        st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=tips['Win'])
        st.write("") 

    st.write("") 

    # 第二排
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    with d4:
        st.metric("穩定度 R²", f"{kpi['R Squared']:.2f}", help=tips['RSQ'])
        with st.popover("📊 穩定度", use_container_width=True):
             range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_rsq")
             df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
             st.plotly_chart(get_mini_chart(df_show, 'R Squared', '#9575CD', '穩定度走勢'), use_container_width=True)
    d5.empty()

@st.fragment
def draw_kelly_fragment(kpi):
    st.markdown("<h4 style='text-align: center; color: #888; margin-top: 10px;'>Position Sizing (Kelly)</h4>", unsafe_allow_html=True)
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
        cal_obj = calendar.Calendar(firstweekday=6)
        month_days = cal_obj.monthdayscalendar(y, m)
        win_bg, win_txt = "#e0f7fa", "#006064"; loss_bg, loss_txt = "#ffebee", "#c62828"
        html = "<table class='cal-table'><thead><tr>" + "".join([f"<th class='cal-th'>{d}</th>" for d in ["SUN","MON","TUE","WED","THU","FRI","SAT"]]) + "</tr></thead><tbody>"
        for week in month_days:
            html += "<tr>"
            for day in week:
                if day == 0: html += "<td class='cal-td' style='border:none; box-shadow:none;'></td>"; continue
                date_key = f"{y}-{m:02d}-{day:02d}"
                day_pnl = daily_pnl.get(date_key, 0)
                style, pnl_text = "", "-"
                if date_key in daily_pnl and day_pnl != 0:
                    style = f"background-color: {win_bg}; color: {win_txt};" if day_pnl > 0 else f"background-color: {loss_bg}; color: {loss_txt};"
                    pnl_text = f"{'+' if day_pnl>0 else '-'}${abs(day_pnl):,.0f}"
                html += f"<td class='cal-td' style='{style}'><div class='day-content'><div class='day-num'>{day}</div><div class='day-pnl'>{pnl_text}</div></div></td>"
            html += "</tr>"
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
        
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
    df_trends = calculate_trends(df_kpi)

    # 1. KPI 區塊
    draw_kpi_cards_with_charts(kpi, df_trends)
    
    st.markdown("---")
    
    # 2. 凱利公式
    draw_kelly_fragment(kpi)
    
    # 3. 日曆
    draw_calendar_fragment(df_cal, chart_theme)
