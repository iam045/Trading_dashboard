import streamlit as st
import pandas as pd
import numpy as np
import calendar
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 0. UI 風格與 CSS 注入器 (UI Master Class)
# ==========================================

def inject_custom_css(theme_mode):
    """
    根據選擇的模式注入 CSS 樣式
    """
    css = ""
    
    if theme_mode == "💎 現代極簡 (Modern)":
        css = """
        <style>
            /* 全局字體與背景優化 */
            .stApp { background-color: #f8f9fa; }
            
            /* Metric 卡片樣式 */
            div[data-testid="stMetric"] {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                padding: 15px;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
                transition: transform 0.2s;
            }
            div[data-testid="stMetric"]:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            }
            div[data-testid="stMetricLabel"] { font-size: 14px; color: #6b7280; }
            div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 700; color: #111827; }
            
            /* Tab 樣式 */
            .stTabs [data-baseweb="tab-list"] { gap: 10px; }
            .stTabs [data-baseweb="tab"] {
                height: 40px; white-space: pre-wrap; background-color: #fff; border-radius: 8px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #eee; gap: 1px;
            }
            .stTabs [aria-selected="true"] { background-color: #eef2ff !important; color: #4f46e5 !important; border-color: #c7d2fe !important; }
        </style>
        """
        chart_theme = "plotly_white"
        
    elif theme_mode == "🌑 暗夜操盤 (Dark Pro)":
        css = """
        <style>
            /* Metric 卡片樣式 - 暗黑版 */
            div[data-testid="stMetric"] {
                background-color: #1e1e1e;
                border: 1px solid #333;
                padding: 10px 15px;
                border-radius: 4px;
                border-left: 3px solid #00e676; /* 螢光綠裝飾 */
            }
            div[data-testid="stMetricLabel"] { font-family: 'Consolas', monospace; color: #888; text-transform: uppercase; letter-spacing: 1px; font-size: 12px; }
            div[data-testid="stMetricValue"] { font-family: 'Consolas', monospace; color: #fff; }
            div[data-testid="stMetricDelta"] svg { fill: #00e676 !important; }
            
            /* 全局文字 */
            p, label, span { color: #cfcfcf !important; }
        </style>
        """
        chart_theme = "plotly_dark"
        
    else: # 📑 經典資訊流 (Classic)
        css = """
        <style>
            div[data-testid="stMetric"] {
                background-color: #fff;
                border-bottom: 2px solid #ccc;
                padding: 10px;
            }
            div[data-testid="stMetricValue"] { color: #2c3e50; font-family: 'Georgia', serif; }
        </style>
        """
        chart_theme = "simple_white"

    st.markdown(css, unsafe_allow_html=True)
    return chart_theme

# ==========================================
# 1. 基礎運算與資料讀取
# ==========================================

def clean_numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '').str.strip(), errors='coerce')

def get_expectancy_data(xls):
    target_sheet = next((name for name in xls.sheet_names if "期望值" in name), None)
    if not target_sheet:
        return None, "找不到含有 '期望值' 的分頁"

    try:
        df = pd.read_excel(xls, sheet_name=target_sheet, header=14)
        if df.shape[1] < 14:
            return None, "期望值表格欄位不足 14 欄"

        df_clean = df.iloc[:, [0, 1, 10, 11, 13]].copy()
        df_clean.columns = ['Date', 'Strategy', 'Risk_Amount', 'PnL', 'R']

        df_clean['Date'] = df_clean['Date'].ffill() 
        df_clean = df_clean.dropna(subset=['Strategy']) 
        df_clean = df_clean.dropna(subset=['Date'])
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
    if not daily_sheets:
        return None, "找不到含有 '日報表' 的分頁", "無"
    
    daily_sheets.sort(reverse=True)
    target_sheets = daily_sheets[:2]
    
    all_dfs = []
    error_msg = ""
    for sheet in target_sheets:
        try:
            df = pd.read_excel(xls, sheet_name=sheet, header=4)
            if df.shape[1] < 8: continue 
                
            df_cal = df.iloc[:, [0, 7]].copy() 
            df_cal.columns = ['Date', 'DayPnL']
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['Date'] = pd.to_datetime(df_cal['Date'], errors='coerce')
            df_cal = df_cal.dropna(subset=['Date'])
            df_cal['Date'] = df_cal['Date'].dt.normalize()
            df_cal['DayPnL'] = clean_numeric(df_cal['DayPnL'])
            df_cal = df_cal.fillna(0)
            all_dfs.append(df_cal)
        except Exception as e:
            error_msg += f"讀取 {sheet} 失敗; "
            continue

    if not all_dfs:
        return None, f"無法讀取有效數據。{error_msg}", "無資料"

    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df = final_df.sort_values('Date')
    info_str = f"僅讀取最新 2 個月: {', '.join(target_sheets)}"
    
    return final_df, None, info_str

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
    corr = np.corrcoef(x, y)[0, 1]
    return corr ** 2

def calculate_kpis(df):
    total = len(df)
    if total == 0: return None
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    
    # 基礎數據
    total_pnl = df['PnL'].sum()
    win_rate = len(wins) / total
    
    # 期望值與因子
    avg_win = wins['PnL'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['PnL'].mean()) if len(losses) > 0 else 0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0
    
    gross_win = wins['PnL'].sum()
    gross_loss = abs(losses['PnL'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    
    # 期望值 (Custom R)
    total_risk = df['Risk_Amount'].sum()
    exp_custom = total_pnl / total_risk if total_risk > 0 else 0
    
    # Kelly
    full_kelly = (win_rate - (1 - win_rate) / payoff) if payoff > 0 else 0
    
    # 進階
    max_win, max_loss = calculate_streaks(df)
    r_sq = calculate_r_squared(df)
    
    return {
        "Total PnL": total_pnl, "Total Trades": total, "Win Rate": win_rate,
        "Payoff Ratio": payoff, "Profit Factor": pf, "Expectancy": exp_custom,
        "Max Win Streak": max_win, "Max Loss Streak": max_loss, "R Squared": r_sq,
        "Full Kelly": full_kelly
    }

def generate_calendar_html(year, month, pnl_dict, theme_mode):
    """
    根據不同風格生成不同顏色的日曆
    """
    cal_obj = calendar.Calendar(firstweekday=6)
    month_days = cal_obj.monthdayscalendar(year, month)
    
    # 風格配色定義
    if "Modern" in theme_mode:
        bg_col = "#ffffff"
        text_col = "#333"
        win_bg = "#dcfce7"; win_txt = "#166534" # 柔和綠
        loss_bg = "#fee2e2"; loss_txt = "#991b1b" # 柔和紅
        border_col = "#f3f4f6"
    elif "Dark" in theme_mode:
        bg_col = "#262626"
        text_col = "#ddd"
        win_bg = "#064e3b"; win_txt = "#4ade80" # 深綠底亮綠字
        loss_bg = "#450a0a"; loss_txt = "#f87171" # 深紅底亮紅字
        border_col = "#404040"
    else: # Classic
        bg_col = "#fff"
        text_col = "#000"
        win_bg = "#ccffcc"; win_txt = "#006400"
        loss_bg = "#ffcccc"; loss_txt = "#8b0000"
        border_col = "#ccc"

    html = f"""
    <style>
        .cal-table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; }}
        .cal-th {{ text-align: center; color: #888; font-size: 11px; padding: 8px 0; border-bottom: 1px solid {border_col}; }}
        .cal-td {{ 
            height: 80px; vertical-align: top; border: 1px solid {border_col}; padding: 4px; position: relative; 
            background-color: {bg_col}; color: {text_col};
        }}
        .day-num {{ font-size: 12px; color: #aaa; margin-bottom: 2px; }}
        .day-pnl {{ font-size: 13px; font-weight: bold; text-align: right; position: absolute; bottom: 6px; right: 6px; }}
    </style>
    <table class="cal-table"><thead><tr>
    <th class="cal-th">SUN</th><th class="cal-th">MON</th><th class="cal-th">TUE</th><th class="cal-th">WED</th><th class="cal-th">THU</th><th class="cal-th">FRI</th><th class="cal-th">SAT</th>
    </tr></thead><tbody>
    """
    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += f"<td class='cal-td' style='background-color: {bg_col}; opacity: 0.5;'></td>"
                continue
            
            date_key = f"{year}-{month:02d}-{day:02d}"
            day_pnl = pnl_dict.get(date_key, 0)
            has_trade = (date_key in pnl_dict) and (day_pnl != 0)
            
            style = ""
            pnl_text = ""
            if has_trade:
                if day_pnl > 0:
                    style = f"background-color: {win_bg}; color: {win_txt};"
                    pnl_text = f"+${day_pnl:,.0f}"
                elif day_pnl < 0:
                    style = f"background-color: {loss_bg}; color: {loss_txt};"
                    pnl_text = f"-${abs(day_pnl):,.0f}"
                else:
                    pnl_text = "$0"
            
            html += f"<td class='cal-td' style='{style}'><div class='day-num'>{day}</div><div class='day-pnl'>{pnl_text}</div></td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# ==========================================
# 2. 進階計算：趨勢分析 (全局運算+切片)
# ==========================================

def calculate_trends(df, mode='cumulative', window=50):
    df = df.sort_values('Date').reset_index(drop=True).copy()
    df['Original_Trade_Num'] = df.index + 1
    
    # 預計算
    df['gross_win'] = df['PnL'].apply(lambda x: x if x > 0 else 0)
    df['gross_loss'] = df['PnL'].apply(lambda x: abs(x) if x <= 0 else 0)
    df['is_win'] = (df['PnL'] > 0).astype(int)
    df['is_loss'] = (df['PnL'] <= 0).astype(int)
    
    # 全局累計
    s_pnl = df['PnL'].cumsum()
    s_risk = df['Risk_Amount'].cumsum()
    s_g_win = df['gross_win'].cumsum()
    s_g_loss = df['gross_loss'].cumsum()
    s_c_win = df['is_win'].cumsum()
    s_c_loss = df['is_loss'].cumsum()

    # KPI
    df['Expectancy'] = s_pnl / s_risk.replace(0, np.nan)
    df['Profit Factor'] = (s_g_win / s_g_loss.replace(0, np.nan)).fillna(10).clip(upper=10)
    
    avg_win = s_g_win / s_c_win.replace(0, np.nan)
    avg_loss = s_g_loss / s_c_loss.replace(0, np.nan)
    df['Payoff Ratio'] = avg_win / avg_loss.replace(0, np.nan)
    
    # R2
    equity = df['PnL'].cumsum()
    x = pd.Series(df.index, index=df.index)
    df['R Squared'] = equity.expanding(min_periods=3).corr(x) ** 2

    df = df.fillna(0)
    
    # Recent 模式切片
    if mode == 'recent':
        df = df.tail(window).copy()
    
    return df

# ==========================================
# 3. UI 顯示邏輯 (Fragments)
# ==========================================

@st.fragment
def draw_kelly_fragment(kpi):
    # 簡單的 CSS 調整讓 Slider 和 Selectbox 對齊
    k1, k2, k3, k4 = st.columns([1.2, 1.2, 1, 1])
    with k1: 
        capital = st.number_input("目前本金", value=300000, step=10000)
    with k2: 
        fraction_options = [1/5, 1/6, 1/7, 1/8]
        kelly_frac = st.selectbox("凱利倍數", fraction_options, index=2, format_func=lambda x: f"1/{int(1/x)} Kelly")
        
    full_kelly_val = kpi.get('Full Kelly', 0)
    adj_kelly = max(0, full_kelly_val * kelly_frac)
    risk_amt = capital * adj_kelly
    
    k3.metric("建議倉位 %", f"{adj_kelly*100:.2f}%")
    k4.metric("建議單筆風險", f"${risk_amt:,.0f}")

@st.fragment
def draw_bottom_fragment(df_cal, sheet_info_cal, df_kpi, theme_mode, chart_theme):
    tab1, tab2 = st.tabs(["📅 交易日曆", "📈 趨勢分析"])
    
    # --- Tab 1: 日曆 ---
    with tab1:
        if df_cal is not None and not df_cal.empty:
            df_cal['DateStr'] = df_cal['Date'].dt.strftime('%Y-%m-%d')
            daily_pnl = df_cal.groupby('DateStr')['DayPnL'].sum().to_dict()
            unique_months = df_cal['Date'].dt.to_period('M').drop_duplicates().sort_values(ascending=False)
            
            if len(unique_months) > 0:
                c_sel, _ = st.columns([1, 4])
                with c_sel:
                    sel_period = st.selectbox("選擇月份", unique_months, index=0, key='cal_month_selector')
                
                y, m = sel_period.year, sel_period.month
                month_pnl = df_cal[df_cal['Date'].dt.to_period('M') == sel_period]['DayPnL']
                
                c_cal, c_stat = st.columns([3, 1])
                with c_cal:
                    st.markdown(f"**{sel_period.strftime('%B %Y')}**")
                    st.markdown(generate_calendar_html(y, m, daily_pnl, theme_mode), unsafe_allow_html=True)
                
                with c_stat:
                    # 統計數據卡片化
                    m_pnl = month_pnl.sum()
                    m_win = month_pnl[month_pnl > 0].count()
                    m_loss = month_pnl[month_pnl < 0].count()
                    m_rate = m_win / (m_win + m_loss) if (m_win + m_loss) > 0 else 0
                    
                    st.metric("月損益", f"${m_pnl:,.0f}")
                    st.metric("月勝率", f"{m_rate:.1%}")
                    st.write(f"📈 獲利: **{m_win}** 天")
                    st.write(f"📉 虧損: **{m_loss}** 天")
            else:
                st.info("無有效月份")
        else:
            st.warning("無日報表資料")

    # --- Tab 2: 趨勢 ---
    with tab2:
        if df_kpi is not None and not df_kpi.empty:
            total = len(df_kpi)
            
            # 控制列容器化
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    mode = st.radio("顯示模式", ["Cumulative (全歷史)", "Recent (最近 N 筆)"], horizontal=True)
                
                win_size = 50
                mode_key = 'cumulative'
                if "Recent" in mode:
                    with c2:
                        win_size = st.slider("分析筆數", 10, max(10, total), min(50, total), 10)
                    mode_key = 'recent'
                    start = max(1, total - win_size + 1)
                    st.caption(f"目前顯示: 第 {start} 筆 ~ 第 {total} 筆 (數值為累計，僅顯示尾端)")
                
            df_t = calculate_trends(df_kpi, mode_key, win_size)
            
            if not df_t.empty:
                # 繪圖設定 (依風格調整顏色)
                line_colors = ['#636EFA', '#00CC96', '#EF553B', '#AB63FA']
                if "Dark" in theme_mode:
                    line_colors = ['#29b6f6', '#00e676', '#ff1744', '#d500f9'] # 螢光色
                
                fig = make_subplots(rows=2, cols=2, vertical_spacing=0.15,
                                    subplot_titles=("期望值 (Expectancy)", "獲利因子 (Profit Factor)", 
                                                    "盈虧比 (Payoff Ratio)", "穩定度 (R Squared)"))
                
                hover = "日期: %{x}<br>數值: %{y:.2f}<br>序號: %{customdata[0]}<extra></extra>"
                
                # 簡化繪圖代碼
                metrics = [('Expectancy', 0), ('Profit Factor', 1), ('Payoff Ratio', 2), ('R Squared', 3)]
                for col_name, idx in metrics:
                    r, c = (idx // 2) + 1, (idx % 2) + 1
                    fig.add_trace(go.Scatter(
                        x=df_t['Date'], y=df_t[col_name],
                        customdata=df_t[['Original_Trade_Num']], hovertemplate=hover,
                        mode='lines', name=col_name,
                        line=dict(color=line_colors[idx], width=2)
                    ), row=r, col=c)

                fig.update_layout(height=500, template=chart_theme, margin=dict(l=20,r=20,t=40,b=20), showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{theme_mode}_{mode_key}")
            else:
                st.info("無數據")
        else:
            st.info("無數據")

# ==========================================
# 4. 主程式進入點
# ==========================================

def display_expectancy_lab(xls):
    # 1. 最上方放置風格切換器 (Radio Button 橫向)
    st.markdown("### 🎨 介面風格設定")
    theme_mode = st.radio(
        "", 
        ["💎 現代極簡 (Modern)", "🌑 暗夜操盤 (Dark Pro)", "📑 經典資訊流 (Classic)"], 
        index=0, 
        horizontal=True,
        label_visibility="collapsed"
    )
    st.markdown("---") # 分隔線
    
    # 注入 CSS 並取得圖表主題
    chart_theme = inject_custom_css(theme_mode)

    # 讀取資料
    df_kpi, err_kpi = get_expectancy_data(xls)
    df_cal, err_cal, _ = get_daily_report_data(xls)

    if err_kpi: st.warning(f"KPI 讀取錯誤: {err_kpi}"); return
    if df_kpi is None or df_kpi.empty: st.info("無資料"); return

    # 計算 KPI
    kpi = calculate_kpis(df_kpi)
    
    # 2. 顯示 KPI (會自動應用 CSS 樣式)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("總損益 (Net PnL)", f"${kpi['Total PnL']:,.0f}", help="淨損益總和")
    c2.metric("期望值 (Exp)", f"{kpi['Expectancy']:.2f} R", help="每單位風險預期獲利")
    c3.metric("獲利因子 (PF)", f"{kpi['Profit Factor']:.2f}", delta=">1.5 佳" if kpi['Profit Factor']>1.5 else None)
    c4.metric("盈虧比 (Payoff)", f"{kpi['Payoff Ratio']:.2f}")
    c5.metric("勝率 (Win Rate)", f"{kpi['Win Rate']*100:.1f}%")
    
    # 增加一點間距
    st.write("") 
    
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("總交易次數", f"{kpi['Total Trades']} 筆")
    d2.metric("最大連勝", f"{kpi['Max Win Streak']} 次", delta="High", delta_color="normal")
    d3.metric("最大連敗", f"{kpi['Max Loss Streak']} 次", delta="Risk", delta_color="inverse")
    d4.metric("曲線穩定度 (R²)", f"{kpi['R Squared']:.2f}")
    d5.empty()
    
    st.markdown("---")

    # 3. 資金管理 (局部刷新)
    draw_kelly_fragment(kpi)
    
    # 4. 底部圖表 (傳入風格參數)
    draw_bottom_fragment(df_cal, None, df_kpi, theme_mode, chart_theme)
