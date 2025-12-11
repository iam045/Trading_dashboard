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
    """
    鎖定現代極簡風格 (Modern Minimalist)
    """
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
            color: #333;
        }

        .stApp { background-color: #f8f9fa; }

        .block-container { text-align: center; }
        h1, h2, h3, p { text-align: center !important; }

        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #eee;
            padding: 20px 10px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        }
        
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px);
            border-color: #81C7D4;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 14px; color: #888; justify-content: center; width: 100%;
        }

        div[data-testid="stMetricValue"] {
            font-size: 26px; font-weight: 600; color: #333; text-align: center;
        }

        .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; }
        .stTabs [data-baseweb="tab"] { background-color: transparent; border: none; font-weight: 600; color: #aaa; }
        .stTabs [aria-selected="true"] { color: #81C7D4 !important; border-bottom: 2px solid #81C7D4 !important; }
        
        .stSelectbox, .stNumberInput, .stSlider { text-align: center; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
    return "plotly_white"

# ==========================================
# 1. 基礎運算與資料讀取
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
    except Exception as e:
        return None, f"讀取期望值失敗: {e}"

def get_daily_report_data(xls):
    sheet_names = xls.sheet_names
    daily_sheets = [s for s in sheet_names if "日報表" in s]
    if not daily_sheets: return None, "找不到含有 '日報表' 的分頁", "無"
    
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

    if not all_dfs: return None, "無法讀取有效數據", "無資料"
    return pd.concat(all_dfs, ignore_index=True).sort_values('Date'), None, ""

def calculate_streaks(df):
    pnl = df['PnL'].values
    max_win = max_loss = curr_win = curr_loss = 0
    for val in pnl:
        if val > 0:
            curr_win += 1; curr_loss = 0
            if curr_win > max_win: max_win = curr_win
        elif val <= 0:
            curr_loss += 1; curr_win = 0
            if curr_loss > max_loss: max_loss = curr_loss
    return max_win, max_loss

def calculate_r_squared(df):
    if len(df) < 2: return 0
    y = df['R'].cumsum().values
    x = np.arange(len(y))
    return (np.corrcoef(x, y)[0, 1]) ** 2

def calculate_kpis(df):
    total = len(df)
    if total == 0: return None
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    total_pnl = df['PnL'].sum()
    win_rate = len(wins) / total
    
    # KPI 卡片使用的 R 盈虧比
    avg_win_r = df[df['R'] > 0]['R'].mean() if len(wins) > 0 else 0
    avg_loss_r = abs(df[df['R'] <= 0]['R'].mean()) if len(losses) > 0 else 0
    payoff_r = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
    
    # 獲利因子 (維持金額)
    pf = wins['PnL'].sum() / abs(losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')
    
    # 期望值 (總損益/總風險)
    total_risk = df['Risk_Amount'].sum()
    exp_custom = total_pnl / total_risk if total_risk > 0 else 0
    
    # 凱利公式 (使用 R Payoff)
    full_kelly = (win_rate - (1 - win_rate) / payoff_r) if payoff_r > 0 else 0
    
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff_r, 
        "Profit Factor": pf, "Expectancy": exp_custom,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq,
        "Full Kelly": full_kelly
    }

def generate_calendar_html(year, month, pnl_dict):
    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(year, month)
    
    bg_col, text_col = "#ffffff", "#333"
    win_bg, win_txt = "#e0f7fa", "#006064"
    loss_bg, loss_txt = "#ffebee", "#c62828"
    border_col = "#f1f1f1"

    html = f"""
    <style>
        .cal-table {{ width: 100%; border-collapse: separate; border-spacing: 5px; font-family: 'Roboto', sans-serif; margin: 0 auto; }}
        .cal-th {{ text-align: center; color: #aaa; font-size: 10px; font-weight: 400; padding: 10px 0; }}
        .cal-td {{ 
            height: 70px; width: 14%; vertical-align: middle; 
            border-radius: 12px; background-color: {bg_col}; color: {text_col};
            box-shadow: 0 2px 5px rgba(0,0,0,0.02); border: 1px solid {border_col};
            position: relative; transition: all 0.2s;
        }}
        .cal-td:hover {{ border-color: #81C7D4; transform: translateY(-2px); }}
        .day-content {{ display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; }}
        .day-num {{ font-size: 12px; color: #bbb; margin-bottom: 2px; }}
        .day-pnl {{ font-size: 13px; font-weight: 600; }}
    </style>
    <table class="cal-table"><thead><tr>
    <th class="cal-th">SUN</th><th class="cal-th">MON</th><th class="cal-th">TUE</th><th class="cal-th">WED</th><th class="cal-th">THU</th><th class="cal-th">FRI</th><th class="cal-th">SAT</th>
    </tr></thead><tbody>
    """
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td class='cal-td' style='border:none; box-shadow:none;'></td>"
                continue
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
# 2. 進階計算：趨勢分析 (已修正 R 邏輯)
# ==========================================

def calculate_trends(df, mode='cumulative', window=50):
    df = df.sort_values('Date').reset_index(drop=True).copy()
    df['Original_Trade_Num'] = df.index + 1
    
    # --- 1. 期望值 & 獲利因子 (維持原本邏輯) ---
    df['gross_win'] = df['PnL'].apply(lambda x: x if x > 0 else 0)
    df['gross_loss'] = df['PnL'].apply(lambda x: abs(x) if x <= 0 else 0)
    
    s_pnl = df['PnL'].cumsum()
    s_risk = df['Risk_Amount'].cumsum()
    s_g_win = df['gross_win'].cumsum()
    s_g_loss = df['gross_loss'].cumsum()
    
    df['Expectancy'] = s_pnl / s_risk.replace(0, np.nan) # 期望值 = 總損益 / 總初始風險 (累計)
    df['Profit Factor'] = (s_g_win / s_g_loss.replace(0, np.nan)).fillna(10).clip(upper=10)

    # --- 2. 盈虧比 Payoff Ratio (修正為 R based) ---
    # 分離 R 值
    df['win_r_val'] = df['R'].apply(lambda x: x if x > 0 else 0)
    df['loss_r_val'] = df['R'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    
    # 累計 R
    s_win_r = df['win_r_val'].cumsum()
    s_loss_r = df['loss_r_val'].cumsum()
    
    # 累計筆數
    s_win_count = df['is_win'].cumsum()
    s_loss_count = (df.index + 1) - s_win_count
    
    # 累計平均 R
    cum_avg_win_r = s_win_r / s_win_count.replace(0, np.nan)
    cum_avg_loss_r = s_loss_r / s_loss_count.replace(0, np.nan)
    
    # 計算趨勢指標
    df['Payoff Ratio'] = cum_avg_win_r / cum_avg_loss_r.replace(0, np.nan)
    
    # --- 3. 穩定度 R² ---
    equity = df['PnL'].cumsum()
    df['R Squared'] = equity.expanding(min_periods=3).corr(pd.Series(df.index)) ** 2
    
    df = df.fillna(0)
    if mode == 'recent': df = df.tail(window).copy()
    return df

# ==========================================
# 3. UI 顯示邏輯 (Fragments)
# ==========================================

@st.fragment
def draw_kelly_fragment(kpi):
    st.markdown("<h4 style='text-align: center; color: #888;'>Position Sizing (Kelly)</h4>", unsafe_allow_html=True)
    c_center = st.columns([1, 2, 2, 2, 2, 1]) 
    
    with c_center[1]: 
        capital = st.number_input("目前本金", value=300000, step=10000)
    
    with c_center[2]: 
        fraction_options = [1/4, 1/5, 1/6, 1/7, 1/8]
        kelly_frac = st.selectbox("凱利倍數", fraction_options, index=1, format_func=lambda x: f"1/{int(1/x)} Kelly")
        
    win_rate = kpi.get('Win Rate', 0)
    payoff_r = kpi.get('Payoff Ratio', 0) # R Payoff
    full_kelly_val = kpi.get('Full Kelly', 0)
    
    adj_kelly = max(0, full_kelly_val * kelly_frac)
    risk_amt = capital * adj_kelly
    
    help_percent_calc = f"""
    【凱利公式 % 計算詳解】
    
    基礎公式: K = W - ( (1-W) / R )
    
    變數代入:
    • 勝率 (W): {win_rate*100:.1f}%
    • 盈虧比 (R): {payoff_r:.2f} (R倍數)
    
    1. 完整凱利 (Full Kelly):
       {win_rate:.2f} - ((1 - {win_rate:.2f}) / {payoff_r:.2f}) 
       = {full_kelly_val*100:.2f}%
    
    2. 調整後建議 (Fractional):
       完整值 {full_kelly_val*100:.2f}% × 選定倍數 (1/{int(1/kelly_frac)})
       = {adj_kelly*100:.2f}%
    """

    with c_center[3]:
        st.metric("建議倉位 %", f"{adj_kelly*100:.2f}%", help=help_percent_calc)
    
    with c_center[4]:
        st.metric("建議單筆風險", f"${risk_amt:,.0f}")

@st.fragment
def draw_bottom_fragment(df_cal, sheet_info_cal, df_kpi, chart_theme):
    tab1, tab2 = st.tabs(["📅 交易日曆", "📈 趨勢分析"])
    
    with tab1:
        if df_cal is not None and not df_cal.empty:
            df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
            daily_pnl = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
            unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
            
            if len(unique_months) > 0:
                c_a, c_b, c_c = st.columns([2, 1, 2])
                with c_b:
                    sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector', label_visibility="collapsed")
                
                y, m = sel_period.year, sel_period.month
                month_data = df_cal[df_cal['Date'].dt.to_period('M') == sel_period]
                month_pnl_series = month_data['DayPnL']
                
                m_total_pnl = month_pnl_series.sum()
                wins, losses = month_pnl_series[month_pnl_series > 0], month_pnl_series[month_pnl_series < 0]
                day_max_win = wins.max() if not wins.empty else 0
                day_max_loss = losses.min() if not losses.empty else 0

                c_cal, c_stat = st.columns([3, 1])
                with c_cal:
                    st.markdown(f"<h3 style='margin-bottom: 20px;'>{sel_period.strftime('%B %Y')}</h3>", unsafe_allow_html=True)
                    st.markdown(generate_calendar_html(y, m, daily_pnl), unsafe_allow_html=True)
                with c_stat:
                    st.markdown("#### 月度摘要")
                    st.metric("本月淨損益", f"${m_total_pnl:,.0f}")
                    st.metric("日最大獲利", f"+${day_max_win:,.0f}")
                    st.metric("日最大虧損", f"-${abs(day_max_loss):,.0f}")
                    st.write(f"📈 獲利: **{len(wins)}** 天")
                    st.write(f"📉 虧損: **{len(losses)}** 天")
            else: st.info("無有效月份")
        else: st.warning("無日報表資料")

    with tab2:
        if df_kpi is not None and not df_kpi.empty:
            with st.container():
                c1, c2, c3 = st.columns([1, 2, 1])
                with c2: mode = st.radio("顯示模式", ["Cumulative (全歷史)", "Recent (最近 N 筆)"], horizontal=True)
                
                win_size = 50
                mode_key = 'cumulative'
                if "Recent" in mode:
                    c_sl1, c_sl2, c_sl3 = st.columns([1, 2, 1])
                    with c_sl2: win_size = st.slider("分析筆數", 10, max(10, len(df_kpi)), min(50, len(df_kpi)), 10)
                    mode_key = 'recent'
                
            df_t = calculate_trends(df_kpi, mode_key, win_size)
            if not df_t.empty:
                line_colors = ['#81C7D4', '#FF8A65', '#BA68C8', '#4DB6AC']
                fig = make_subplots(rows=2, cols=2, vertical_spacing=0.15, subplot_titles=("期望值 (Exp)", "獲利因子 (PF)", "盈虧比 (R Payoff)", "穩定度 (R²)"))
                hover = "日期: %{x}<br>數值: %{y:.2f}<br>序號: %{customdata[0]}<extra></extra>"
                metrics = [('Expectancy', 0), ('Profit Factor', 1), ('Payoff Ratio', 2), ('R Squared', 3)]
                
                for col_name, idx in metrics:
                    r, c = (idx // 2) + 1, (idx % 2) + 1
                    fig.add_trace(go.Scatter(x=df_t['Date'], y=df_t[col_name], customdata=df_t[['Original_Trade_Num']], hovertemplate=hover, mode='lines', name=col_name, line=dict(color=line_colors[idx], width=2.5)), row=r, col=c)

                fig.update_layout(height=500, template=chart_theme, margin=dict(l=20,r=20,t=40,b=20), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{mode_key}")

# ==========================================
# 4. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    chart_theme = inject_custom_css()
    st.markdown("<h1>TRADING PERFORMANCE</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #999; margin-bottom: 40px;'>現代極簡交易儀表板</p>", unsafe_allow_html=True)

    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, err_cal, _ = get_daily_report_data(xls)

    if err_kpi: st.warning(f"KPI 讀取錯誤: {err_kpi}"); return
    if df_kpi is None or df_kpi.empty: st.info("無資料"); return

    kpi = calculate_kpis(df_kpi)
    
    help_exp = "定義: 每單位風險的平均獲利 (Total PnL / Total Risk)。\n公式: 總損益 ÷ 總初始風險"
    help_pf = "定義: 總獲利金額與總虧損金額的比率，大於 1.5 為佳。\n公式: 總獲利金額 ÷ 總虧損金額"
    help_payoff = "定義: 平均每筆獲利 R 與平均每筆虧損 R 的比例。\n公式: Avg Win R ÷ Avg Loss R"
    help_win = "定義: 獲利交易次數佔總交易次數的比例。\n公式: 獲利筆數 ÷ 總交易筆數"
    help_rsq = "定義: 權益曲線的回歸判定係數，越接近 1 代表獲利越穩定，波動越小。"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益", f"${kpi['Total PnL']:,.0f}")
    c2.metric("期望值", f"{kpi['Expectancy']:.2f} R", help=help_exp)
    c3.metric("獲利因子", f"{kpi['Profit Factor']:.2f}", help=help_pf)
    c4.metric("盈虧比 (R)", f"{kpi['Payoff Ratio']:.2f}", help=help_payoff)
    c5.metric("勝率", f"{kpi['Win Rate']*100:.1f}%", help=help_win)
    
    st.write("") 
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次")
    d4.metric("穩定度 R²", f"{kpi['R Squared']:.2f}", help=help_rsq)
    d5.empty()
    
    st.markdown("---")
    draw_kelly_fragment(kpi)
    st.markdown("---")
    draw_bottom_fragment(df_cal, None, df_kpi, chart_theme)
