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

        /* 右側資訊欄位共用 (第 8, 9 欄) */
        .summary-td {
            width: 150px; 
            vertical-align: middle;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding-left: 10px !important;
        }
        
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
    """讀取期望值分頁 (修復版：採用名稱對應避免 ILOC 崩潰)"""
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet: return None, "找不到含有 '期望值' 的分頁"
    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        
        # 定義 Excel 欄位名稱對應 (處理刪除欄位問題)
        mapping = {
            '日期': 'Date',
            '策略': 'Strategy',
            '1R單位': 'Risk_Amount',
            '損益': 'PnL',
            '損益R': 'R'
        }
        
        # 僅抓取存在的標題並重新命名
        existing_cols = [col for col in mapping.keys() if col in df.columns]
        df_clean = df[existing_cols].copy().rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        
        # 補全缺失欄位預設值
        if 'Strategy' not in df_clean.columns: df_clean['Strategy'] = 'Standard'
        if 'Date' in df_clean.columns: df_clean['Date'] = df_clean['Date'].ffill()
        
        # 資料清理與轉型
        df_clean = df_clean.dropna(subset=['Date'])
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.normalize()
        
        for col in ['Risk_Amount', 'PnL', 'R']:
            if col in df_clean.columns:
                df_clean[col] = clean_numeric(df_clean[col])
        
        # 移除關鍵數據缺失的行
        df_clean = df_clean.dropna(subset=['PnL', 'R'])
        
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
    avg_loss_r = abs(df[df['R'] <= 0]['R'].mean()) if len(losses) > 0 else 1
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    
    # 期望值計算基準
    exp_r = df['R'].mean() 
    
    max_win, max_loss = calculate_streaks(df); r_sq = calculate_r_squared(df)
    full_kelly = (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, "Profit Factor": pf, "Expectancy": exp_r,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq, "Full Kelly": full_kelly
    }

def calculate_trends(df):
    df = df.reset_index(drop=True).copy()
    df['Running_EV'] = df['R'].expanding().mean()
    df['Running_PF'] = (df['PnL'].apply(lambda x: x if x > 0 else 0).cumsum() / 
                        df['PnL'].apply(lambda x: abs(x) if x <= 0 else 0).cumsum().replace(0, np.nan)).fillna(1)
    df['Running_RSQ'] = df['R'].cumsum().expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
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
    fig.add_trace(go.Scatter(x=df_show['Date'], y=df_show[col_name], mode='lines', line=dict(color=color, width=2), fill='tozeroy', fillcolor=fill_color))
    fig.update_layout(height=60, margin=dict(l=0, r=0, t=5, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
    return fig

@st.fragment
def draw_kpi_cards_with_charts(kpi, df_t):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("總損益", f"${kpi['Total PnL']:,.0f}"); st.write("")
    with c2: 
        st.metric("期望值", f"{kpi['Expectancy']:.3f} R")
        st.plotly_chart(get_sparkline(df_t, 'Running_EV', '#FF8A65'), use_container_width=True, config={'displayModeBar': False})
    with c3:
        st.metric("獲利因子", f"{kpi['Profit Factor']:.2f}")
        st.plotly_chart(get_sparkline(df_t, 'Running_PF', '#BA68C8'), use_container_width=True, config={'displayModeBar': False})
    with c4:
        st.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}")
        st.plotly_chart(get_sparkline(df_t, 'Running_EV', '#4DB6AC'), use_container_width=True, config={'displayModeBar': False})
    with c5: st.metric("勝率", f"{kpi['Win Rate']*100:.1f}%"); st.write("")

    st.write("") 
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    with d4:
        st.metric("穩定度 R²", f"{kpi['R Squared']:.2f}")
        st.plotly_chart(get_sparkline(df_t, 'Running_RSQ', '#9575CD'), use_container_width=True, config={'displayModeBar': False})
    d5.empty()

@st.fragment
def draw_kelly_fragment(kpi):
    st.markdown("<h4 style='text-align: center; color: #888; margin-top: 10px;'>Position Sizing (Kelly)</h4>", unsafe_allow_html=True)
    c_center = st.columns([1, 2, 2, 2, 2, 1]) 
    with c_center[1]: capital = st.number_input("目前本金", value=1000000, step=100000)
    with c_center[2]: kelly_frac = st.selectbox("凱利倍數", [1/4, 1/5, 1/6, 1/8], index=1, format_func=lambda x: f"1/{int(1/x)} Kelly")
    adj_kelly = max(0, kpi.get('Full Kelly', 0) * kelly_frac)
    with c_center[3]: st.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
    with c_center[4]: st.metric("建議單筆風險", f"${capital * adj_kelly:,.0f}")

@st.fragment
def draw_calendar_fragment(df_cal, theme_mode):
    if df_cal is None or df_cal.empty: st.warning("無日報表資料"); return
    df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
    daily_pnl_map = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
    unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
    
    st.markdown("---")
    c_sel, _ = st.columns([1, 4])
    with c_sel: sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
    
    y, m = sel_period.year, sel_period.month
    df_month = df_cal[(df_cal['Date'].dt.year == y) & (df_cal['Date'].dt.month == m)].sort_values('Date')
    m_pnl = df_month['DayPnL'].sum()

    # 月統計資訊與繪圖 (保留原設計)
    if not df_month.empty:
        col_c1, col_c2 = st.columns(2)
        color = '#ef5350' if m_pnl >= 0 else '#26a69a'
        fig1 = go.Figure(go.Scatter(x=df_month['Date'], y=df_month['DayPnL'].cumsum(), mode='lines', line=dict(color=color, width=3), fill='tozeroy', fillcolor=hex_to_rgba(color, 0.2)))
        fig1.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        with col_c1: st.plotly_chart(fig1, use_container_width=True)
        
        fig2 = go.Figure(go.Bar(x=df_month['Date'], y=df_month['DayPnL'], marker_color=[('#ef5350' if v >= 0 else '#26a69a') for v in df_month['DayPnL']]))
        fig2.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        with col_c2: st.plotly_chart(fig2, use_container_width=True)

    # HTML 月曆生成 (9 欄佈局)
    st.markdown(f"<h3 style='text-align: left !important;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)
    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(y, m)
    
    # ... 此處繼續 9 欄 HTML 生成邏輯 (由於長度限制，邏輯已簡化，完全對齊您提供的 HTML 格式)
    # [註: 由於此處需要大量 HTML 字串生成，我確保其結構完全符合您提供的 Sun-Sat + 2個 Summary 欄位]
    html = """<div class="cal-container"><table class='cal-table'><thead><tr><th class='cal-th'>Sun</th><th class='cal-th'>Mon</th><th class='cal-th'>Tue</th><th class='cal-th'>Wed</th><th class='cal-th'>Thu</th><th class='cal-th'>Fri</th><th class='cal-th'>Sat</th><th class='cal-th'></th><th class='cal-th'></th></tr></thead><tbody>"""
    week_count = 1
    m_stats = [{"title": "本月損益", "val": f"${m_pnl:,.0f}"}, {"title": "日勝率", "val": f"{(len(df_month[df_month['DayPnL']>0])/len(df_month[df_month['DayPnL']!=0]) if len(df_month[df_month['DayPnL']!=0])>0 else 0)*100:.1f}%"}, {"title": "最大獲利", "val": f"${df_month['DayPnL'].max():,.0f}"}, {"title": "最大虧損", "val": f"${df_month['DayPnL'].min():,.0f}"}]

    for idx, week in enumerate(month_days):
        html += "<tr>"
        week_pnl = 0
        active_days = 0
        for day in week:
            if day == 0: html += "<td class='cal-td' style='background:transparent; border:none;'></td>"
            else:
                pnl = daily_pnl_map.get(f"{y}-{m:02d}-{day:02d}", 0)
                cls = "cal-td" + (" bg-green" if pnl > 0 else (" bg-red" if pnl < 0 else ""))
                pnl_str = f"<div class='day-pnl'>{'+' if pnl>0 else '-'}${abs(pnl):,.0f}</div><div class='day-info'>Trade</div>" if pnl != 0 else ""
                html += f"<td class='{cls}'><div class='day-num'>{day}</div>{pnl_str}</td>"
                if pnl != 0: week_pnl += pnl; active_days += 1
        
        # 右側 Summary 欄位 (第 8, 9 欄)
        w_cls = "text-green" if week_pnl >= 0 else "text-red"
        html += f"<td class='summary-td'><div class='week-card'><div class='week-title'>Week {week_count}</div><div class='week-pnl {w_cls}'>${abs(week_pnl):,.0f}</div><div class='week-days'>{active_days} days</div></div></td>"
        week_count += 1
        if idx < len(m_stats):
            html += f"<td class='summary-td'><div class='month-card'><div class='month-title'>{m_stats[idx]['title']}</div><div class='month-val'>{m_stats[idx]['val']}</div></div></td>"
        else: html += "<td class='summary-td'></td>"
        html += "</tr>"
    
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# 4. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    chart_theme = inject_custom_css()
    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, _, _ = get_daily_report_data(xls)
    
    if err_kpi: st.warning(f"KPI 讀取錯誤: {err_kpi}"); return
    if df_kpi is None or df_kpi.empty: st.info("無資料"); return

    kpi = calculate_kpis(df_kpi)
    df_trends = calculate_trends(df_kpi)
    
    draw_kpi_cards_with_charts(kpi, df_trends)
    st.markdown("---")
    draw_kelly_fragment(kpi)
    draw_calendar_fragment(df_cal, chart_theme)
