import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go

# ==========================================
# 0. UI 風格與 CSS 注入器
# ==========================================

def inject_custom_css():
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; color: #333; }
        .stApp { background-color: #f8f9fa; }
        .block-container { text-align: center; }
        
        h1, h2, h3, p { text-align: center !important; }

        /* --- Metric 卡片樣式 --- */
        div[data-testid="column"]:has(div[data-testid="stMetric"]) {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
            padding: 20px 15px 10px 15px;
            min-height: 160px;
            transition: transform 0.2s;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        div[data-testid="column"]:has(div[data-testid="stMetric"]):hover {
            border-color: #81C7D4;
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.05);
        }

        /* --- Metric 數值微調 --- */
        div[data-testid="stMetric"] { background-color: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
        div[data-testid="stMetricLabel"] { font-size: 13px; color: #888; justify-content: center; width: 100%; }
        div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 600; color: #333; }

        /* --- Popover 按鈕 --- */
        div[data-testid="column"] div[data-testid="stPopover"] button {
            border: none !important;
            background: transparent !important;
            color: #81C7D4 !important;
            width: 100% !important;
            margin-top: 10px !important;
            border-top: 1px solid #f5f5f5 !important;
            border-radius: 0px 0px 12px 12px !important;
        }

        /* --- 左對齊設定 --- */
        .stTabs [data-baseweb="tab-list"] { justify-content: flex-start !important; gap: 20px; }
        .stSelectbox, .stNumberInput, .stSlider { text-align: left !important; }
        div[data-baseweb="select"] { text-align: left !important; }
        .cal-selector div[data-baseweb="select"] { text-align: left; }

        /* --- 新版日曆樣式 (9欄佈局: 7天 + 1週 + 1月) --- */
        .cal-container { width: 100%; overflow-x: auto; }
        .cal-table { 
            width: 100%; 
            min-width: 1200px; /* 確保在小螢幕上不會擠成一團 */
            border-collapse: separate; 
            border-spacing: 6px; 
            margin: 0 auto; 
            table-layout: fixed; 
        }
        
        /* 日期單元格 (左邊 7 欄) */
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
        
        .cal-th { padding-bottom: 10px; color: #888; font-size: 13px; font-weight: 500; text-transform: uppercase; }

        .day-num { font-size: 14px; color: #aaa; position: absolute; top: 8px; right: 10px; font-weight: bold; }
        .day-pnl { margin-top: 22px; font-size: 15px; font-weight: 700; text-align: center; }
        .day-info { font-size: 11px; color: inherit; opacity: 0.8; text-align: center; margin-top: 2px; }

        /* --- 右側欄位共用樣式 --- */
        .summary-td {
            width: 150px; /* 固定右側欄寬度 */
            vertical-align: middle;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding-left: 10px !important;
        }
        
        /* 週結算卡片 */
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

        /* 月統計卡片 */
        .month-card {
            background-color: #fff;
            border-radius: 12px;
            padding: 10px;
            text-align: center;
            border: 1px solid #eeeeee;
            border-left: 3px solid #81C7D4; /* 左側藍線區分 */
            box-shadow: 0 2px 6px rgba(0,0,0,0.02);
            height: 80px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .month-title { font-size: 11px; color: #666; margin-bottom: 4px; }
        .month-val { font-size: 16px; font-weight: 700; color: #333; }
        
        /* 顏色定義 */
        .text-green { color: #00897b; }
        .text-red { color: #e53935; }
        .bg-green { background-color: #e0f2f1 !important; border-color: #b2dfdb !important; color: #004d40 !important; }
        .bg-red { background-color: #ffebee !important; border-color: #ffcdd2 !important; color: #b71c1c !important; }
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
            # 這裡維持讀取第0欄(日期)與第7欄(損益)，請確認 Excel 中 PnL 是否在 H 欄 (Index 7)
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
    df = df.sort_values('Date').reset_index(drop=True).copy()
    df['win_r_val'] = df['R'].apply(lambda x: x if x > 0 else 0)
    df['loss_r_val'] = df['R'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    
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
        fill='tozeroy', fillcolor=fill_color 
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
        "Exp": "每下單一次能賺多少。因為分母所以是R。\n公式: 總損益 ÷ 總停損最大風險",
        "PF": "想成總收入是總成本的 N 倍。\n公式: 總獲利金額 ÷ 總虧損金額",
        "Payoff": "「單次」交易的品質。\n公式: Avg Win R ÷ Avg Loss R",
        "Win": "獲利交易次數佔總交易次數的比例。\n公式: 獲利筆數 ÷ 總交易筆數",
        "RSQ": "權益曲線的回歸判定係數，越接近 1 代表獲利越穩定。"
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("總損益", f"${kpi['Total PnL']:,.0f}")
        st.write("") 
    with c2:
        st.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=tips['Exp'])
        with st.popover("📊 期望值", use_container_width=True):
            range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_exp")
            df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
            st.plotly_chart(get_mini_chart(df_show, 'Expectancy', '#FF8A65', '期望值走勢'), use_container_width=True)
    with c3:
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=tips['PF'])
        with st.popover("📊 獲利因子", use_container_width=True):
            range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_pf")
            df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
            st.plotly_chart(get_mini_chart(df_show, 'Profit Factor', '#BA68C8', '獲利因子走勢'), use_container_width=True)
    with c4:
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=tips['Payoff'])
        with st.popover("📊 盈虧比", use_container_width=True):
            range_mode = st.radio("顯示範圍", ["全歷史", "近 50 筆", "近 100 筆"], horizontal=True, key="range_payoff")
            df_show = df_t if range_mode == "全歷史" else (df_t.tail(50) if range_mode == "近 50 筆" else df_t.tail(100))
            st.plotly_chart(get_mini_chart(df_show, 'Payoff Ratio', '#4DB6AC', '盈虧比走勢'), use_container_width=True)
    with c5:
        st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=tips['Win'])
        st.write("") 

    st.write("") 
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
    daily_pnl_map = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    if len(unique_months) == 0: st.info("無有效月份"); return

    st.markdown("---")
    
    # 1. 月份選擇器 (靠左)
    c_header_left, _ = st.columns([1, 4])
    with c_header_left:
        st.markdown('<div class="cal-selector">', unsafe_allow_html=True)
        sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    y, m = sel_period.year, sel_period.month
    
    # 2. 計算該月數據 (包含邏輯修正：排除PnL為0的日子)
    mask_month = (df_cal['Date'].dt.year == y) & (df_cal['Date'].dt.month == m)
    df_month = df_cal[mask_month].sort_values('Date') 

    # 篩選實際交易日 (PnL != 0)
    df_active = df_month[df_month['DayPnL'] != 0]

    m_pnl = df_month['DayPnL'].sum()
    total_active_days = len(df_active) # 分母只算有交易的日子
    win_days = df_active[df_active['DayPnL'] > 0]
    loss_days = df_active[df_active['DayPnL'] < 0]
    m_win_rate = (len(win_days) / total_active_days) if total_active_days > 0 else 0
    day_max_win = win_days['DayPnL'].max() if not win_days.empty else 0
    day_max_loss = loss_days['DayPnL'].min() if not loss_days.empty else 0

    # 3. 月度走勢圖 (維持在選擇器下方)
    if not df_month.empty:
        color_up = '#ef5350' # Soft Red
        color_down = '#26a69a' # Teal Green
        
        df_month['CumPnL'] = df_month['DayPnL'].cumsum()
        
        col_chart1, col_chart2 = st.columns(2)
        
        # Chart 1: Area Chart
        trend_color = color_up if m_pnl >= 0 else color_down
        fill_color_rgba = hex_to_rgba(trend_color, 0.2)
        
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df_month['Date'], y=df_month['CumPnL'],
            mode='lines',
            line=dict(color=trend_color, width=3),
            fill='tozeroy',
            fillcolor=fill_color_rgba,
            name='累積損益'
        ))
        fig1.update_layout(
            title=dict(text="本月累積損益走勢", font=dict(size=14), x=0),
            height=280,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(showgrid=False, showticklabels=True, tickformat='%m/%d'),
            yaxis=dict(showgrid=True, gridcolor='#eee', zeroline=True, zerolinecolor='#ccc'),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        with col_chart1: st.plotly_chart(fig1, use_container_width=True)
        
        # Chart 2: Bar Chart
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
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        with col_chart2: st.plotly_chart(fig2, use_container_width=True)

    st.write("") 
    
    # 4. 標題與日曆表格
    st.markdown(f"<h3 style='text-align: left !important; margin-bottom: 15px;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)

    cal_obj = calendar.Calendar(firstweekday=6) # Sunday start
    month_days = cal_obj.monthdayscalendar(y, m)

    # 準備月統計卡片數據
    month_stats_data = [
        {"title": "本月淨損益", "val": f"${m_pnl:,.0f}", "color": "text-green" if m_pnl >=0 else "text-red"},
        {"title": "本月日勝率", "val": f"{m_win_rate*100:.1f}%", "color": ""},
        {"title": "日最大獲利", "val": f"${day_max_win:,.0f}", "color": "text-green"},
        {"title": "日最大虧損", "val": f"${day_max_loss:,.0f}", "color": "text-red"}
    ]
    
    # HTML 建構：9欄佈局 (7天 + 1週 + 1月)
    html = """<div class="cal-container"><table class='cal-table'><thead><tr><th class='cal-th'>Sun</th><th class='cal-th'>Mon</th><th class='cal-th'>Tue</th><th class='cal-th'>Wed</th><th class='cal-th'>Thu</th><th class='cal-th'>Fri</th><th class='cal-th'>Sat</th><th class='cal-th' style='width: 150px;'></th><th class='cal-th' style='width: 150px;'></th></tr></thead><tbody>"""

    week_count = 1
    
    for idx, week in enumerate(month_days):
        html += "<tr>"
        
        # --- 計算該週統計數據 ---
        week_pnl = 0
        active_days = 0
        for day in week:
            if day == 0: continue
            date_key = f"{y}-{m:02d}-{day:02d}"
            pnl = daily_pnl_map.get(date_key, 0)
            if pnl != 0:
                week_pnl += pnl
                active_days += 1
        
        # --- 生成左側 7 天的格子 ---
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
        
        # --- 第 8 欄：週結算卡片 ---
        w_pnl_class = "text-green" if week_pnl >= 0 else "text-red"
        w_pnl_sign = "+" if week_pnl > 0 else ("-" if week_pnl < 0 else "")
        w_pnl_str = f"${abs(week_pnl):,.0f}" if active_days > 0 else "$0"
        
        show_week_card = any(d != 0 for d in week)
        
        if show_week_card:
            card_html = f"<div class='week-card'><div class='week-title'>Week {week_count}</div><div class='week-pnl {w_pnl_class}'>{w_pnl_sign}{w_pnl_str}</div><div class='week-days'>{active_days} active days</div></div>"
            html += f"<td class='summary-td'>{card_html}</td>"
            week_count += 1
        else:
            html += "<td class='summary-td'></td>"

        # --- 第 9 欄：月統計卡片 ---
        if idx < len(month_stats_data):
            m_stat = month_stats_data[idx]
            color_cls = m_stat["color"]
            m_card_html = f"""
            <div class='month-card'>
                <div class='month-title'>{m_stat['title']}</div>
                <div class='month-val {color_cls}'>{m_stat['val']}</div>
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
    
    # 3. 日曆 (含週結算 + 月統計 + 月走勢圖)
    draw_calendar_fragment(df_cal, chart_theme)
