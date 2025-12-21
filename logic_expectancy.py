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

        /* --- Metric 卡片容器 (增強版) --- */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 15px 10px 15px;
            min-height: 180px; /* 稍微加高以容納 Sparkline */
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
        .stSelectbox, .stNumberInput, .stSlider { text-align: left !important; }
        div[data-baseweb="select"] { text-align: left !important; }
        .cal-selector div[data-baseweb="select"] { text-align: left; }
        .modebar { display: none !important; } /* 隱藏 Plotly 工具列 */

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
        
        /* 日曆標頭 */
        .cal-th { padding-bottom: 10px; color: #888; font-size: 13px; font-weight: 500; text-transform: uppercase; }

        /* 日期單元格 (左 7 欄) */
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

        /* 右側資訊欄位共用 (第 8, 9 欄) */
        .summary-td {
            width: 150px; 
            vertical-align: middle;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding-left: 10px !important;
        }
        
        /* 第 8 欄：週結算卡片 */
        .week-card {
            background-color: #fff;
            border-radius: 12px;
            padding: 10px;
            text-align: center;
            border: 1px solid #e0e0e0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.03);
            height: 80px; 
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .week-title { font-size: 12px; color: #81C7D4; font-weight: bold; margin-bottom: 4px; }
        .week-pnl { font-size: 18px; font-weight: 700; margin-bottom: 2px; }
        .week-days { font-size: 11px; color: #999; }

        /* 第 9 欄：月統計卡片 */
        .month-card {
            background-color: #fff;
            border-radius: 12px;
            padding: 10px;
            text-align: center;
            border: 1px solid #eeeeee;
            border-left: 4px solid #81C7D4; 
            box-shadow: 0 2px 6px rgba(0,0,0,0.02);
            height: 80px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .month-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; }
        .month-val { font-size: 20px; font-weight: 800; color: #000000 !important; }
        
        /* 通用顏色 class */
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
    """將含有逗號的字串轉換為數字，錯誤則回傳 NaN"""
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    """讀取期望值分頁"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到含有 '期望值' 的分頁"
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        if df.shape[1] < 14: return None, "期望值表格欄位不足 14 欄"
        # 欄位選取：日期, 策略, 風險金額, 損益, R
        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']
        df_clean['Date'] = df_clean['Date'].ffill() 
        df_clean = df_clean.dropna(subset=['Strategy', 'Date'])
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.normalize()
        
        # 數值清理
        for col in ['Risk_Amount', 'PnL', 'R']: 
            df_clean[col] = clean_numeric(df_clean[col])
            
        df_clean = df_clean.dropna(subset=['PnL', 'Risk_Amount'])
        df_clean = df_clean[df_clean['Risk_Amount'] > 0]
        return df_clean.sort_values('Date'), None
    except Exception as e: return None, f"讀取期望值失敗: {e}"

def get_daily_report_data(xls):
    """讀取最新的兩個日報表"""
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
            df_cal = df.iloc[:, [0, 7]].copy() # 日期, 當日損益
            df_cal.columns = ['Date', 'DayPnL']
            df_cal['Date'] = pd.to_datetime(df_cal['Date'], errors='coerce').dt.normalize()
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['DayPnL'] = clean_numeric(df_cal['DayPnL']).fillna(0)
            all_dfs.append(df_cal)
        except: continue
    if not all_dfs: return None, "無效數據", "無"
    return pd.concat(all_dfs, ignore_index=True).sort_values('Date'), None, ""

def calculate_streaks(df):
    """計算連勝與連敗"""
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
    """計算全域 KPI"""
    total = len(df); wins = df[df['PnL'] > 0]; losses = df[df['PnL'] <= 0]
    total_pnl = df['PnL'].sum(); win_rate = len(wins) / total if total > 0 else 0
    
    avg_win_r = df[df['R'] > 0]['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = abs(df[df['R'] <= 0]['R'].mean()) if len(losses) > 0 else 0
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    total_risk = df['Risk_Amount'].sum()
    exp_custom = total_pnl / total_risk if total_risk > 0 else 0
    full_kelly = (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    
    max_win, max_loss = calculate_streaks(df); r_sq = calculate_r_squared(df)
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, "Profit Factor": pf, "Expectancy": exp_custom,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def calculate_trends(df):
    """計算累積數據供圖表使用"""
    df = df.sort_values('Date').reset_index(drop=True).copy()
    df['win_r_val'] = df['R'].apply(lambda x: x if x > 0 else 0)
    df['loss_r_val'] = df['R'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    
    s_pnl = df['PnL'].cumsum()
    s_risk = df['Risk_Amount'].cumsum()
    s_r_cumsum = df['R'].cumsum() # [修正] 新增累積 R 值
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
    
    # [修正] R Squared 走勢圖改用 s_r_cumsum (累積R) 來計算，以與 KPI 卡片數值同步
    df['R Squared'] = s_r_cumsum.expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
    
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

def get_sparkline(df_t, col_name, color):
    """
    產生 Sparkline (微型趨勢圖)
    特點：極簡、無座標軸、高度低、適合嵌入卡片
    """
    fill_color = hex_to_rgba(color, 0.1)
    
    # 取最近 50 筆數據來畫微型圖，反應近期走勢
    df_show = df_t.tail(50) if len(df_t) > 50 else df_t
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_show['Date'], y=df_show[col_name], 
        mode='lines', 
        name=col_name,
        line=dict(color=color, width=2),
        fill='tozeroy', 
        fillcolor=fill_color,
        hoverinfo='y' 
    ))
    
    fig.update_layout(
        height=60, 
        margin=dict(l=0, r=0, t=5, b=0), 
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        hovermode='x unified'
    )
    
    return fig

@st.fragment
def draw_kpi_cards_with_charts(kpi, df_t):
    """繪製最上方的 KPI 卡片列 (使用 Sparklines)"""
    tips = {
        "Exp": "期望值 (Expectancy):\n每承擔 1R 風險，預期能賺回多少 R。\n公式: 總損益 ÷ 總風險金額",
        "PF": "獲利因子 (Profit Factor):\n總獲利金額是總虧損金額的幾倍。",
        "Payoff": "盈虧比 (Payoff Ratio):\n平均賺的一筆是平均賠的一筆的幾倍。",
        "Win": "勝率 (Win Rate):\n獲利交易次數 ÷ 總交易次數",
        "RSQ": "R Squared (穩定度):\n權益曲線的平滑程度。此處採用 R (風險倍數) 計算，反映交易邏輯的一致性。"
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    
    # 1. 總損益
    with c1:
        st.metric("總損益", f"${kpi['Total PnL']:,.0f}")
        st.write("") 
    
    # 2. 期望值 + Sparkline
    with c2:
        st.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=tips['Exp'])
        st.plotly_chart(
            get_sparkline(df_t, 'Expectancy', '#FF8A65'), 
            use_container_width=True, 
            config={'displayModeBar': False}
        )
            
    # 3. 獲利因子 + Sparkline
    with c3:
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=tips['PF'])
        st.plotly_chart(
            get_sparkline(df_t, 'Profit Factor', '#BA68C8'), 
            use_container_width=True, 
            config={'displayModeBar': False}
        )
            
    # 4. 盈虧比 + Sparkline
    with c4:
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=tips['Payoff'])
        st.plotly_chart(
            get_sparkline(df_t, 'Payoff Ratio', '#4DB6AC'), 
            use_container_width=True, 
            config={'displayModeBar': False}
        )
            
    # 5. 勝率
    with c5:
        st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=tips['Win'])
        st.write("") 

    st.write("") 
    
    # 第二排統計數據
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    
    # 穩定度 + Sparkline
    with d4:
        st.metric("穩定度 R²", f"{kpi['R Squared']:.2f}", help=tips['RSQ'])
        st.plotly_chart(
            get_sparkline(df_t, 'R Squared', '#9575CD'), 
            use_container_width=True, 
            config={'displayModeBar': False}
        )
    d5.empty()

@st.fragment
def draw_kelly_fragment(kpi):
    """繪製凱利公式計算器"""
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
    • 勝率: {win_rate*100:.1f}% | 盈虧比: {payoff_r:.2f}
    建議倉位 = 完整凱利值 × {kelly_frac:.2f}
    """
    with c_center[3]: st.metric("建議倉位 %", f"{adj_kelly*100:.2f}%", help=help_text)
    with c_center[4]: st.metric("建議單筆風險", f"${risk_amt:,.0f}")

@st.fragment
def draw_calendar_fragment(df_cal, theme_mode):
    """繪製包含月走勢圖、日曆與右側統計欄位的複合元件"""
    if df_cal is None or df_cal.empty:
        st.warning("無日報表資料"); return

    df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
    daily_pnl_map = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    if len(unique_months) == 0: st.info("無有效月份"); return

    st.markdown("---")
    
    # 1. 月份選擇器
    c_header_left, _ = st.columns([1, 4])
    with c_header_left:
        st.markdown('<div class="cal-selector">', unsafe_allow_html=True)
        sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    y, m = sel_period.year, sel_period.month
    
    # 2. 計算該月數據
    mask_month = (df_cal['Date'].dt.year == y) & (df_cal['Date'].dt.month == m)
    df_month = df_cal[mask_month].sort_values('Date') 

    # 3. 計算月統計數據 (用於右側第 9 欄)
    m_pnl = df_month['DayPnL'].sum()
    # 僅計算有實際損益的日子 (排除 PnL=0)
    df_active = df_month[df_month['DayPnL'] != 0]
    
    win_days = df_active[df_active['DayPnL'] > 0]
    loss_days = df_active[df_active['DayPnL'] < 0]
    m_win_rate = (len(win_days) / len(df_active)) if len(df_active) > 0 else 0
    day_max_win = win_days['DayPnL'].max() if not win_days.empty else 0
    day_max_loss = loss_days['DayPnL'].min() if not loss_days.empty else 0

    # 4. 繪製月度走勢圖 (選擇器下方)
    if not df_month.empty:
        color_up = '#ef5350' # 紅色 (獲利)
        color_down = '#26a69a' # 綠色 (虧損)
        
        df_month['CumPnL'] = df_month['DayPnL'].cumsum()
        
        col_chart1, col_chart2 = st.columns(2)
        
        # 左圖: 累積損益 (Area Chart)
        trend_color = color_up if m_pnl >= 0 else color_down
        fill_color_rgba = hex_to_rgba(trend_color, 0.2)
        
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df_month['Date'], y=df_month['CumPnL'],
            mode='lines',
            line=dict(color=trend_color, width=3),
            fill='tozeroy', fillcolor=fill_color_rgba,
            name='累積損益'
        ))
        fig1.update_layout(
            title=dict(text="本月累積損益走勢", font=dict(size=14), x=0),
            height=280,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(showgrid=False, showticklabels=True, tickformat='%m/%d'),
            yaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, zerolinecolor='#ccc'),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        with col_chart1: st.plotly_chart(fig1, use_container_width=True)
        
        # 右圖: 每日損益 (Bar Chart)
        bar_colors = [color_up if v >= 0 else color_down for v in df_month['DayPnL']]
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=df_month['Date'], y=df_month['DayPnL'],
            marker_color=bar_colors,
            name='日損益'
        ))
        fig2.update_layout(
            title=dict(text="本月每日損益", font=dict(size=14), x=0),
            height=280,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(showgrid=False, showticklabels=True, tickformat='%m/%d'),
            yaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, zerolinecolor='#ccc'),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        with col_chart2: st.plotly_chart(fig2, use_container_width=True)

    st.write("") 
    
    # 5. 月份標題
    st.markdown(f"<h3 style='text-align: left !important; margin-bottom: 15px;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)

    # 6. 建構 HTML 表格
    cal_obj = calendar.Calendar(firstweekday=6) # Sunday start
    month_days = cal_obj.monthdayscalendar(y, m)

    # 準備右側第9欄的數據列表
    month_stats_data = [
        {"title": "本月淨損益", "val": f"${m_pnl:,.0f}"},
        {"title": "本月日勝率", "val": f"{m_win_rate*100:.1f}%"},
        {"title": "日最大獲利", "val": f"${day_max_win:,.0f}"},
        {"title": "日最大虧損", "val": f"${day_max_loss:,.0f}"}
    ]
    
    html = """<div class="cal-container"><table class='cal-table'><thead><tr><th class='cal-th'>Sun</th><th class='cal-th'>Mon</th><th class='cal-th'>Tue</th><th class='cal-th'>Wed</th><th class='cal-th'>Thu</th><th class='cal-th'>Fri</th><th class='cal-th'>Sat</th><th class='cal-th' style='width: 150px;'></th><th class='cal-th' style='width: 150px;'></th></tr></thead><tbody>"""

    week_count = 1
    
    for idx, week in enumerate(month_days):
        html += "<tr>"
        
        # --- (A) 預計算該週數據 ---
        week_pnl = 0
        active_days_in_week = 0
        for day in week:
            if day == 0: continue
            date_key = f"{y}-{m:02d}-{day:02d}"
            pnl = daily_pnl_map.get(date_key, 0)
            if pnl != 0:
                week_pnl += pnl
                active_days_in_week += 1
        
        # --- (B) 生成日期格 (第 1~7 欄) ---
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='background: transparent; border: none; box-shadow: none;'></td>"
                continue
            
            date_key = f"{y}-{m:02d}-{day:02d}"
            day_pnl = daily_pnl_map.get(date_key, 0)
            
            td_class = "cal-td"
            pnl_html = ""
            if day_pnl != 0:
                color_class = "bg-green" if day_pnl > 0 else "bg-red"
                td_class += f" {color_class}"
                sign = "+" if day_pnl > 0 else "-"
                pnl_html = f"<div class='day-pnl'>{sign}${abs(day_pnl):,.0f}</div><div class='day-info'>Trade</div>"
            else:
                pnl_html = "<div style='height: 20px;'></div>"

            html += f"<td class='{td_class}'><div class='day-num'>{day}</div>{pnl_html}</td>"
        
        # --- (C) 生成週結算格 (第 8 欄) ---
        w_pnl_class = "text-green" if week_pnl >= 0 else "text-red"
        w_pnl_sign = "+" if week_pnl > 0 else ("-" if week_pnl < 0 else "")
        w_pnl_str = f"${abs(week_pnl):,.0f}" if active_days_in_week > 0 else "$0"
        
        # 只要該週有任何一天不是空白(有日期)，就顯示週卡片框架
        show_week_card = any(d != 0 for d in week)
        
        if show_week_card:
            card_html = f"<div class='week-card'><div class='week-title'>Week {week_count}</div><div class='week-pnl {w_pnl_class}'>{w_pnl_sign}{w_pnl_str}</div><div class='week-days'>{active_days_in_week} active days</div></div>"
            html += f"<td class='summary-td'>{card_html}</td>"
            week_count += 1
        else:
            html += "<td class='summary-td'></td>"

        # --- (D) 生成月統計格 (第 9 欄) ---
        # 依序填入 month_stats_data，填完為止
        if idx < len(month_stats_data):
            m_stat = month_stats_data[idx]
            m_card_html = f"""
            <div class='month-card'>
                <div class='month-title'>{m_stat['title']}</div>
                <div class='month-val'>{m_stat['val']}</div>
            </div>
            """
            html += f"<td class='summary-td'>{m_card_html}</td>"
        else:
            html += "<td class='summary-td'></td>"

        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 4. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    chart_theme = inject_custom_css()
    
    # 讀取資料
    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, err_cal, _ = get_daily_report_data(xls)

    # 基本錯誤檢查
    if err_kpi: st.warning(f"KPI 讀取錯誤: {err_kpi}"); return
    if df_kpi is None or df_kpi.empty: st.info("無 KPI 資料"); return

    # 計算全域指標
    kpi = calculate_kpis(df_kpi)
    df_trends = calculate_trends(df_kpi)

    # 1. 繪製 KPI 卡片區塊
    draw_kpi_cards_with_charts(kpi, df_trends)
    
    st.markdown("---")
    
    # 2. 繪製凱利公式區塊
    draw_kelly_fragment(kpi)
    
    # 3. 繪製日曆複合區塊 (選擇器 -> 圖表 -> 表格)
    draw_calendar_fragment(df_cal, chart_theme)
