import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 0. UI 風格與 CSS 注入器 (Modern Only)
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; }
        h1, h2, h3, p { text-align: center !important; }

        /* Metric 卡片優化 */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #eee;
            padding: 15px 10px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
            text-align: center;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        div[data-testid="stMetric"]:hover { border-color: #81C7D4; }
        div[data-testid="stMetricLabel"] { font-size: 13px; color: #888; justify-content: center; width: 100%; }
        div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 600; color: #333; }

        /* Popover 按鈕優化 (讓它看起來像個小標籤) */
        button[kind="secondary"] {
            border: none;
            background: transparent;
            color: #81C7D4;
            font-size: 0.8rem;
            padding: 0px;
        }
        button[kind="secondary"]:hover {
            color: #5bb0c0;
            background: transparent;
            border: none;
        }

        /* 日曆表格 */
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
        
        /* 隱藏預設圖表選單 */
        .modebar { display: none !important; }
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

    # Metrics Trends
    df['Total PnL'] = s_pnl
    df['Expectancy'] = s_pnl / s_risk.replace(0, np.nan)
    df['Profit Factor'] = (s_g_win / s_g_loss.replace(0, np.nan)).fillna(10).clip(upper=10)
    df['Payoff Ratio'] = (s_win_r / s_win_count) / (s_loss_r / s_loss_count).replace(0, np.nan)
    df['R Squared'] = s_pnl.expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
    
    return df.fillna(0)

# ==========================================
# 2. 繪圖與 UI 元件 (Fragments)
# ==========================================

def get_mini_chart(df_t, col_name, color, title):
    """生成極簡的小趨勢圖 (用於 Popover)"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_t.index, y=df_t[col_name],
        mode='lines', name=col_name,
        line=dict(color=color, width=2),
        fill='tozeroy', fillcolor=f"rgba{color[3:-1]}, 0.1)" # 簡單的填色效果
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14), x=0.5, xanchor='center'),
        height=250, margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False), # 隱藏 X 軸讓畫面乾淨
        yaxis=dict(showgrid=True, gridcolor='#eee'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    return fig

@st.fragment
def draw_kpi_cards_with_charts(kpi, df_t):
    # Tooltips
    tips = {
        "Exp": "定義: 每單位風險的平均獲利。\n公式: 總損益 ÷ 總初始風險",
        "PF": "定義: 總獲利金額與總虧損金額的比率。\n公式: 總獲利金額 ÷ 總虧損金額",
        "Payoff": "定義: 平均每筆獲利 R 與平均每筆虧損 R 的比例。\n公式: Avg Win R ÷ Avg Loss R",
        "Win": "定義: 獲利交易次數佔總交易次數的比例。\n公式: 獲利筆數 ÷ 總交易筆數",
        "RSQ": "定義: 權益曲線的回歸判定係數，越接近 1 代表獲利越穩定。"
    }

    # 第一排 KPI
    c1, c2, c3, c4, c5 = st.columns(5)
    
    # 1. 總損益
    with c1:
        st.metric("總損益", f"${kpi['Total PnL']:,.0f}")
        with st.popover("📈 損益走勢", use_container_width=True):
            st.plotly_chart(get_mini_chart(df_t, 'Total PnL', '#81C7D4', '累計損益曲線 (Total PnL)'), use_container_width=True)

    # 2. 期望值
    with c2:
        st.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=tips['Exp'])
        with st.popover("📈 趨勢圖", use_container_width=True):
            st.plotly_chart(get_mini_chart(df_t, 'Expectancy', '#FF8A65', '期望值走勢 (Expectancy)'), use_container_width=True)

    # 3. 獲利因子
    with c3:
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=tips['PF'])
        with st.popover("📈 趨勢圖", use_container_width=True):
            st.plotly_chart(get_mini_chart(df_t, 'Profit Factor', '#BA68C8', '獲利因子走勢 (PF)'), use_container_width=True)

    # 4. 盈虧比 (R)
    with c4:
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=tips['Payoff'])
        with st.popover("📈 趨勢圖", use_container_width=True):
            st.plotly_chart(get_mini_chart(df_t, 'Payoff Ratio', '#4DB6AC', '盈虧比走勢 (R Payoff)'), use_container_width=True)

    # 5. 勝率 (勝率通常波動小，這裡可以不放圖，或放累計勝率)
    with c5:
        st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=tips['Win'])
        # 這裡留空或也可以加圖，保持對齊
        st.write("") 

    st.write("") # 間距

    # 第二排 KPI (無圖表)
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    with d4:
        st.metric("穩定度 R²", f"{kpi['R Squared']:.2f}", help=tips['RSQ'])
        with st.popover("📈 趨勢圖", use_container_width=True):
             st.plotly_chart(get_mini_chart(df_t, 'R Squared', '#9575CD', '穩定度走勢 (R²)'), use_container_width=True)
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

    c_a, c_b, c_c = st.columns([2, 1, 2])
    with c_b: sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
    
    y, m = sel_period.year, sel_period.month
    month_data = df_cal[df_cal['Date'].dt.to_period('M') == sel_period]
    month_pnl_series = month_data['DayPnL']
    
    m_total_pnl = month_pnl_series.sum()
    wins, losses = month_pnl_series[month_pnl_series > 0], month_pnl_series[month_pnl_series < 0]
    day_max_win = wins.max() if not wins.empty else 0
    day_max_loss = losses.min() if not losses.empty else 0
    
    st.markdown("---")
    c_cal, c_stat = st.columns([3, 1])
    with c_cal:
        st.markdown(f"<h3 style='margin-bottom: 20px;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)
        # 生成日曆 HTML
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
    df_trends = calculate_trends(df_kpi) # 預先計算趨勢

    # 1. KPI 區塊 (包含圖表 Popover)
    draw_kpi_cards_with_charts(kpi, df_trends)
    
    st.markdown("---")
    
    # 2. 凱利公式
    draw_kelly_fragment(kpi)
    
    # 3. 日曆 (不再需要 Tab 2 的趨勢圖，因為已經搬到上面了)
    draw_calendar_fragment(df_cal, chart_theme)
